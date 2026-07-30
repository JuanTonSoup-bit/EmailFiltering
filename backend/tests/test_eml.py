"""Tests for the raw .eml parser and its integration with the engine."""

from __future__ import annotations

from pathlib import Path

from app.analysis import analyze
from app.analysis.eml import parse_eml, parse_eml_file

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "phish_paypal.eml"

RAW_CLEAN = """From: Example News <news@example.com>
To: me@example.com
Subject: Weekly newsletter
Date: Tue, 15 Jul 2026 10:00:00 +0000
Authentication-Results: mx.google.com; spf=pass; dkim=pass; dmarc=pass
Content-Type: text/plain; charset="utf-8"

Just our normal weekly newsletter, nothing to see here.
"""


def test_parse_extracts_sender_domain_and_headers():
    msg = parse_eml(RAW_CLEAN)
    assert msg.from_address == "news@example.com"
    assert msg.from_domain == "example.com"
    assert msg.subject == "Weekly newsletter"
    assert msg.header("authentication-results").startswith("mx.google.com")
    assert "newsletter" in msg.body_text.lower()


def test_clean_eml_scores_low():
    result = analyze(parse_eml(RAW_CLEAN))
    assert result.verdict == "clean"


def test_sample_phish_eml_is_flagged():
    msg = parse_eml_file(SAMPLE)
    assert msg.from_domain == "paypa1-secure-alerts.com"

    result = analyze(msg)
    codes = {f.code for f in result.findings}

    # Typosquatting sender domain + failed authentication should be caught.
    assert "typosquat_domain" in codes
    assert "dmarc_fail" in codes
    assert result.verdict == "suspicious"


def test_sample_phish_link_mismatch_detected():
    result = analyze(parse_eml_file(SAMPLE))
    codes = {f.code for f in result.findings}
    # Anchor text claims paypal.com but href points to a lookalike domain.
    assert "url_mismatch" in codes or "typosquat_link" in codes
