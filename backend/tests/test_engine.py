"""Tests for the detection engine and analyzers."""

from __future__ import annotations

from app.analysis import analyze
from app.analysis.message import ParsedMessage


def make_message(**overrides) -> ParsedMessage:
    defaults = dict(
        gmail_id="test1",
        thread_id="t1",
        headers={},
        subject="Hello",
        from_address="news@example.com",
        from_display="Example News",
        from_domain="example.com",
        reply_to="",
        reply_to_domain="",
        to_address="me@gmail.com",
        date_sent="Tue, 15 Jul 2026 10:00:00 +0000",
        body_text="Just a normal newsletter.",
        body_html="<p>Just a normal newsletter.</p>",
        label_ids=[],
    )
    defaults.update(overrides)
    return ParsedMessage(**defaults)


def test_clean_authenticated_mail_scores_low():
    msg = make_message(
        headers={
            "authentication-results": "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
        }
    )
    result = analyze(msg)
    assert result.verdict == "clean"
    assert result.score < 25


def test_dmarc_fail_adds_weight():
    msg = make_message(
        headers={
            "authentication-results": "mx.google.com; spf=fail; dkim=fail; dmarc=fail"
        }
    )
    result = analyze(msg)
    codes = {f.code for f in result.findings}
    assert "dmarc_fail" in codes
    assert "spf_fail" in codes
    assert result.score >= 50


def test_paypal_display_name_spoof_is_suspicious():
    msg = make_message(
        from_display="PayPal Support",
        from_address="billing@secure-paypa1-alerts.com",
        from_domain="secure-paypa1-alerts.com",
        subject="Your account will be suspended",
        body_text="Verify your account immediately to avoid suspension.",
        headers={
            "authentication-results": "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
        },
    )
    result = analyze(msg)
    codes = {f.code for f in result.findings}
    assert "display_name_spoof" in codes
    assert "credential_request" in codes or "urgency" in codes
    assert result.verdict == "suspicious"


def test_url_mismatch_detected():
    msg = make_message(
        body_html='<a href="http://evil-login.ru/steal">https://www.paypal.com/login</a>',
    )
    result = analyze(msg)
    codes = {f.code for f in result.findings}
    assert "url_mismatch" in codes


def test_ip_url_detected():
    msg = make_message(
        body_html='<a href="http://203.0.113.5/login">Click here</a>',
    )
    result = analyze(msg)
    codes = {f.code for f in result.findings}
    assert "ip_url" in codes


def test_reply_to_mismatch():
    msg = make_message(
        reply_to="attacker@other-domain.xyz",
        reply_to_domain="other-domain.xyz",
    )
    result = analyze(msg)
    codes = {f.code for f in result.findings}
    assert "reply_to_mismatch" in codes


def test_bulk_mail_marked_junk_not_suspicious():
    msg = make_message(
        headers={
            "authentication-results": "mx.google.com; spf=pass; dkim=pass; dmarc=pass",
            "list-unsubscribe": "<mailto:unsub@example.com>",
        },
        body_text="Check out our limited time offer, expires soon!",
    )
    result = analyze(msg)
    assert result.verdict in {"junk", "clean"}
    assert result.verdict != "suspicious"
