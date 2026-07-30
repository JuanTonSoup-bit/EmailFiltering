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
