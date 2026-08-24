"""Tests for the typosquatting / lookalike-domain detector."""

from __future__ import annotations

from app.analysis.typosquat import check_domain


def test_legitimate_brand_domain_is_clean():
    assert check_domain("paypal.com") is None
    assert check_domain("outlook.com") is None  # microsoft-owned
    assert check_domain("gmail.com") is None  # google-owned


def test_unrelated_domain_is_clean():
    assert check_domain("example.com") is None
    assert check_domain("towson.edu") is None


def test_homoglyph_substitution():
    hit = check_domain("paypa1.com")  # digit 1 for letter l
    assert hit is not None
    assert hit.brand == "paypal"
    assert hit.technique == "homoglyph"


def test_typo_edit_distance():
    hit = check_domain("gogle.com")  # missing an 'o'
    assert hit is not None
    assert hit.brand == "google"
    assert hit.technique == "typo"
    assert hit.distance == 1


def test_combosquatting_with_extra_words():
    hit = check_domain("paypal-secure-login.com")
    assert hit is not None
    assert hit.brand == "paypal"
    assert hit.technique == "combo"


def test_tld_swap():
    hit = check_domain("paypal.co")  # real label, wrong TLD
    assert hit is not None
    assert hit.brand == "paypal"
    assert hit.technique == "tld_swap"


def test_subdomain_is_reduced_to_registered_domain():
    # A real PayPal subdomain must not be flagged...
    assert check_domain("account.paypal.com") is None
    # ...but a lookalike under a subdomain still is.
    hit = check_domain("login.paypa1.com")
    assert hit is not None
    assert hit.brand == "paypal"


def test_confidence_is_bounded():
    hit = check_domain("micrsoft.com")
    assert hit is not None
    assert 0.0 < hit.confidence <= 1.0


# --- Regression: first-party infrastructure is not a typosquat -------------
# The first live scan against a real inbox produced exactly two flags, and
# both were false positives of this kind: legitimate Microsoft and Google
# infrastructure domains flagged for containing their own brand name.

import pytest

from app.analysis import analyze
from app.analysis.spoofing import legitimate_brand


@pytest.mark.parametrize(
    "domain,brand",
    [
        ("microsoftonline.com", "microsoft"),
        ("login.microsoftonline.com", "microsoft"),
        ("googleusercontent.com", "google"),
        ("googleapis.com", "google"),
        ("amazonaws.com", "amazon"),
        ("fbcdn.net", "facebook"),
        ("licdn.com", "linkedin"),
        ("paypalobjects.com", "paypal"),
    ],
)
def test_first_party_infrastructure_is_not_a_squat(domain, brand):
    assert check_domain(domain) is None
    assert legitimate_brand(domain) == brand


def test_brand_linking_to_its_own_infrastructure_is_not_flagged():
    """Real Microsoft mail links to microsoftonline.com. That is not
    impersonation, and must not produce a typosquat_link finding."""
    from app.analysis.message import ParsedMessage

    msg = ParsedMessage(
        gmail_id="ms1",
        thread_id="t1",
        headers={
            "authentication-results": "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
        },
        subject="Default Directory invited you to access applications",
        from_address="invites@microsoft.com",
        from_display="Microsoft Invitations",
        from_domain="microsoft.com",
        reply_to="",
        reply_to_domain="",
        to_address="me@gmail.com",
        date_sent="",
        body_text="Accept the invitation.",
        body_html='<p><a href="https://login.microsoftonline.com/redeem">Accept</a></p>',
        label_ids=[],
    )
    result = analyze(msg)
    assert [f.code for f in result.findings] == []
    assert result.verdict == "clean"


def test_real_typosquat_link_still_flagged():
    """The exemption must not disarm the check: a domain that really is
    impersonating a brand the sender does not own still fires."""
    from app.analysis.message import ParsedMessage

    msg = ParsedMessage(
        gmail_id="ph1",
        thread_id="t1",
        headers={
            "authentication-results": "mx.google.com; spf=pass; dkim=pass; dmarc=pass"
        },
        subject="Account notice",
        from_address="noreply@mailer.example.com",
        from_display="Notices",
        from_domain="mailer.example.com",
        reply_to="",
        reply_to_domain="",
        to_address="me@gmail.com",
        date_sent="",
        body_text="Sign in.",
        body_html='<p><a href="https://paypal-secure-login.example/go">Sign in</a></p>',
        label_ids=[],
    )
    result = analyze(msg)
    assert "typosquat_link" in [f.code for f in result.findings]
