"""Tests for the dashboard aggregates and the API routes that serve them.

These use an in-memory SQLite database rather than the real data/phishguard.db
so a test run can never touch, or be influenced by, the developer's actual
scan history.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import ScannedEmail
from app.stats import build_dashboard, window_start


@pytest.fixture()
def session() -> Session:
    # StaticPool keeps every connection pointed at the SAME in-memory
    # database; without it each connection gets its own empty one and the
    # tables created here would be invisible to the next query.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db


def add_email(
    session: Session,
    *,
    verdict: str = "clean",
    days_ago: int = 0,
    domain: str = "example.com",
    score: int = 0,
    spf: str = "pass",
    dkim: str = "pass",
    dmarc: str = "pass",
) -> ScannedEmail:
    # Noon UTC so a test never lands on a day boundary and flakes depending
    # on what time of day it is run.
    when = dt.datetime.now(dt.timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    ) - dt.timedelta(days=days_ago)
    email = ScannedEmail(
        gmail_id=f"msg-{verdict}-{days_ago}-{domain}-{score}-{id(session)}",
        from_address=f"sender@{domain}",
        from_domain=domain,
        subject="Test",
        spf=spf,
        dkim=dkim,
        dmarc=dmarc,
        score=score,
        verdict=verdict,
        findings=[],
        scanned_at=when,
    )
    session.add(email)
    session.commit()
    return email


def test_window_start_covers_whole_calendar_days():
    start = window_start(7)
    assert start.hour == 0 and start.minute == 0 and start.second == 0
    today = dt.datetime.now(dt.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # "Last 7 days" includes today, so the window opens 6 days back.
    assert (today - start).days == 6


def test_totals_and_verdicts(session: Session):
    add_email(session, verdict="clean")
    add_email(session, verdict="junk", score=30, domain="promo.example")
    add_email(session, verdict="suspicious", score=70, domain="paypa1.example")

    stats = build_dashboard(session, days=14)

    assert stats.total_scanned == 3
    assert stats.clean == 1
    assert stats.junk == 1
    assert stats.suspicious == 1
    # "Flagged" is junk + suspicious - clean is never counted as flagged.
    assert stats.total_flagged == 2


def test_window_excludes_older_mail(session: Session):
    add_email(session, verdict="suspicious", days_ago=1, score=70)
    add_email(session, verdict="suspicious", days_ago=40, score=70)

    assert build_dashboard(session, days=7).total_scanned == 1
    assert build_dashboard(session, days=90).total_scanned == 2


def test_window_applies_to_every_aggregate(session: Session):
    """A date filter that only scoped the timeline would put numbers on the
    page that cannot be reconciled with each other."""
    add_email(session, verdict="junk", days_ago=40, domain="old.example", score=30)

    stats = build_dashboard(session, days=7)

    assert stats.total_scanned == 0
    assert stats.top_senders == []
    assert all(
        rate.passed == 0 and rate.failed == 0 and rate.other == 0
        for rate in stats.auth_rates
    )


def test_auth_rates_bucket_pass_fail_and_neither(session: Session):
    add_email(session, spf="pass", dkim="pass", dmarc="pass")
    add_email(session, spf="fail", dkim="fail", dmarc="fail", domain="b.example")
    add_email(session, spf="none", dkim="neutral", dmarc="none", domain="c.example")

    stats = build_dashboard(session, days=14)
    by_mechanism = {rate.mechanism: rate for rate in stats.auth_rates}

    assert {"spf", "dkim", "dmarc"} == set(by_mechanism)
    for rate in by_mechanism.values():
        # Anything that is neither a hard pass nor a hard fail is its own
        # state - a domain with no DMARC record has not failed anything.
        assert (rate.passed, rate.failed, rate.other) == (1, 1, 1)


def test_top_senders_excludes_clean_and_reports_max_score(session: Session):
    add_email(session, verdict="clean", domain="good.example")
    add_email(session, verdict="junk", domain="bad.example", score=30)
    add_email(session, verdict="suspicious", domain="bad.example", score=80)

    stats = build_dashboard(session, days=14)

    assert [s.from_domain for s in stats.top_senders] == ["bad.example"]
    assert stats.top_senders[0].count == 2
    assert stats.top_senders[0].max_score == 80


def test_timeline_buckets_by_day(session: Session):
    add_email(session, verdict="suspicious", days_ago=0, score=70)
    add_email(session, verdict="junk", days_ago=0, score=30, domain="b.example")
    add_email(session, verdict="junk", days_ago=2, score=30, domain="c.example")

    timeline = build_dashboard(session, days=14).timeline
    by_date = {point.date: point for point in timeline}

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    assert by_date[today].suspicious == 1
    assert by_date[today].junk == 1
    # Days with no mail are simply absent; the front end pads the range so
    # the x-axis stays continuous.
    assert len(timeline) == 2
