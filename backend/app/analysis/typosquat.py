"""Typosquatting / lookalike-domain detection against a known-brand list.

Given any domain (a sender's domain, or a domain pulled from a link) this
decides whether it is trying to impersonate one of a set of well-known brands
through a common squatting technique:

  * homoglyph  - visually similar character swaps (paypa1.com, g00gle.com)
  * typo       - small edit-distance change (gogle.com, micrsoft.com)
  * combo      - the brand embedded with extra words (paypal-secure.com)
  * tld_swap   - the real brand label under the wrong TLD (paypal.co)

It is intentionally dependency-light (only tldextract, already a project
dependency) so it can run standalone on any domain string, independent of the
Gmail pipeline. The engine calls it for both the sender domain and link
domains; the CLI (`app.tools.scan_eml --domain`) calls it directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tldextract

from .spoofing import BRAND_DOMAINS

# ASCII look-alike substitutions attackers use to mimic letters.
_HOMOGLYPHS = str.maketrans(
    {
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "6": "g",
        "7": "t",
        "8": "b",
        "9": "g",
        "$": "s",
        "|": "l",
        "!": "i",
    }
)

# Multi-character confusables applied after the single-char translation.
_MULTI_HOMOGLYPHS = (("rn", "m"), ("vv", "w"), ("cl", "d"))

_SPLIT_RE = re.compile(r"[-_.]+")


@dataclass
class TyposquatResult:
    """A domain judged to be impersonating `brand` via `technique`."""

    domain: str  # the registered domain that was checked
    brand: str  # brand being impersonated
    technique: str  # homoglyph | typo | combo | tld_swap
    distance: int  # edit distance to the brand (0 when not distance-based)
    confidence: float  # 0..1, higher is a stronger match

    def describe(self) -> str:
        return f"{self.domain} ~ {self.brand} ({self.technique})"


def _registered(domain: str) -> str:
    """Reduce a host to its registrable domain, e.g. a.paypal.com -> paypal.com."""
    ext = tldextract.extract(domain)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}".lower()
    return domain.strip().lower()


def _normalize(label: str) -> str:
    """Fold homoglyphs so paypa1 -> paypal, g00gle -> google."""
    out = label.lower().translate(_HOMOGLYPHS)
    for src, dst in _MULTI_HOMOGLYPHS:
        out = out.replace(src, dst)
    return out


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _typo_threshold(brand: str) -> int:
    """Allowed edit distance for a `typo` match, scaled to brand length.

    Short brands need a tight bound or unrelated words collide with them;
    longer brands can absorb an extra edit.
    """
    return 1 if len(brand) <= 5 else 2


def check_domain(
    domain: str, brands: dict[str, set[str]] | None = None
) -> TyposquatResult | None:
    """Return the strongest typosquat match for `domain`, or None if it looks
    legitimate / unrelated to any known brand."""
    brands = brands if brands is not None else BRAND_DOMAINS
    reg = _registered(domain)
    if not reg or "." not in reg:
        return None
    label = reg.split(".")[0]
    norm = _normalize(label)

    # Exact legitimate domain for any brand -> not a squat.
    for legit in brands.values():
        if reg in legit:
            return None

    best: TyposquatResult | None = None

    def consider(candidate: TyposquatResult) -> None:
        nonlocal best
        if best is None or candidate.confidence > best.confidence:
            best = candidate

    for brand, legit in brands.items():
        if len(brand) < 4:
            continue  # too short to match reliably (ups, dhl)
        legit_labels = {d.split(".")[0] for d in legit}

        # 1. Homoglyph-only impersonation: the folded label *is* the brand,
        #    but the raw label was disguised (paypa1 -> paypal).
        if norm == brand and norm != label:
            consider(TyposquatResult(reg, brand, "homoglyph", 0, 0.9))
            continue

        # 2. Right brand label, wrong TLD: paypal.co, chase.net. Uses the raw
        #    label so a homoglyphed label under the real TLD stays case (1).
        if label in legit_labels:
            consider(TyposquatResult(reg, brand, "tld_swap", 0, 0.85))
            continue

        # 3. Small typo distance (measured on the folded label).
        dist = _levenshtein(norm, brand)
        if 0 < dist <= _typo_threshold(brand):
            consider(TyposquatResult(reg, brand, "typo", dist, 0.8 - 0.1 * (dist - 1)))
            continue

        # 4. Combosquatting: brand appears with extra words / separators.
        tokens = [t for t in _SPLIT_RE.split(norm) if t]
        if brand in tokens and len(tokens) > 1:
            consider(TyposquatResult(reg, brand, "combo", 0, 0.75))
        elif brand in norm and norm != brand and len(brand) >= 5:
            consider(TyposquatResult(reg, brand, "combo", 0, 0.65))

    return best
