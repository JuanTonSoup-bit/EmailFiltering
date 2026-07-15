"""Aggregation queries powering the dashboard."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ScannedEmail
from .schemas import (
    AuthRate,
    DashboardStats,
    TimePoint,
    TopSender,
    VerdictCount,
)

_PASS = "pass"
_FAIL = "fail"


def _auth_rate(session: Session, column) -> tuple[int, int, int]:
    rows = session.execute(
        select(column, func.count()).group_by(column)
    ).all()
    passed = failed = other = 0
    for value, count in rows:
        if value == _PASS:
            passed += count
        elif value == _FAIL:
            failed += count
        else:
            other += count
    return passed, failed, other


def build_dashboard(session: Session, days: int = 14) -> DashboardStats:
    total = session.scalar(select(func.count()).select_from(ScannedEmail)) or 0

    # Verdict breakdown
    verdict_rows = session.execute(
        select(ScannedEmail.verdict, func.count()).group_by(ScannedEmail.verdict)
    ).all()
    verdicts = {v: c for v, c in verdict_rows}
    verdict_counts = [VerdictCount(verdict=v, count=c) for v, c in verdict_rows]

    suspicious = verdicts.get("suspicious", 0)
    junk = verdicts.get("junk", 0)
    clean = verdicts.get("clean", 0)

    # Auth pass rates
    auth_rates = []
    for mech, col in (
        ("spf", ScannedEmail.spf),
        ("dkim", ScannedEmail.dkim),
        ("dmarc", ScannedEmail.dmarc),
    ):
        p, f, o = _auth_rate(session, col)
        auth_rates.append(AuthRate(mechanism=mech, passed=p, failed=f, other=o))

    # Timeline (per-day verdict counts)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    day = func.strftime("%Y-%m-%d", ScannedEmail.scanned_at)
    timeline_rows = session.execute(
        select(day, ScannedEmail.verdict, func.count())
        .where(ScannedEmail.scanned_at >= since)
        .group_by(day, ScannedEmail.verdict)
        .order_by(day)
    ).all()
    buckets: dict[str, dict[str, int]] = {}
    for date_str, verdict, count in timeline_rows:
        buckets.setdefault(date_str, {})[verdict] = count
    timeline = [
        TimePoint(
            date=date_str,
            clean=vals.get("clean", 0),
            junk=vals.get("junk", 0),
            suspicious=vals.get("suspicious", 0),
        )
        for date_str, vals in sorted(buckets.items())
    ]

    # Top flagged sender domains
    sender_rows = session.execute(
        select(
            ScannedEmail.from_domain,
            func.count(),
            func.max(ScannedEmail.score),
        )
        .where(ScannedEmail.verdict != "clean")
        .where(ScannedEmail.from_domain.is_not(None))
        .group_by(ScannedEmail.from_domain)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    top_senders = [
        TopSender(from_domain=d, count=c, max_score=s)
        for d, c, s in sender_rows
    ]

    return DashboardStats(
        total_scanned=total,
        total_flagged=suspicious + junk,
        suspicious=suspicious,
        junk=junk,
        clean=clean,
        verdicts=verdict_counts,
        auth_rates=auth_rates,
        timeline=timeline,
        top_senders=top_senders,
    )
