"""Social-engineering language heuristics (urgency, credential requests)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

URGENCY_PATTERNS = [
    r"urgent", r"immediately", r"right away", r"as soon as possible",
    r"within \d+ hours", r"final (notice|warning|reminder)",
    r"act now", r"account (will be )?(suspended|closed|locked|disabled)",
    r"suspend(ed)?", r"unusual (activity|sign-?in|login)", r"verify your account",
    r"limited time", r"expires? (today|soon|in \d+)",
]

CREDENTIAL_PATTERNS = [
    r"verify your (account|identity|password|information)",
    r"confirm your (account|identity|password|payment|details)",
    r"update your (payment|billing|password|account)",
    r"log ?in to (verify|confirm|secure|restore)",
    r"click (here|below) to (verify|confirm|log ?in|restore|unlock)",
    r"enter your (password|pin|ssn|social security|card number)",
    r"re-?activate your account",
]

_URGENCY_RE = [re.compile(p, re.IGNORECASE) for p in URGENCY_PATTERNS]
_CREDENTIAL_RE = [re.compile(p, re.IGNORECASE) for p in CREDENTIAL_PATTERNS]


@dataclass
class LanguageFindings:
    urgency_hits: list[str] = field(default_factory=list)
    credential_hits: list[str] = field(default_factory=list)


def analyze_language(subject: str, body_text: str) -> LanguageFindings:
    text = f"{subject}\n{body_text}"
    findings = LanguageFindings()

    for pattern in _URGENCY_RE:
        m = pattern.search(text)
        if m:
            findings.urgency_hits.append(m.group(0).lower())
    for pattern in _CREDENTIAL_RE:
        m = pattern.search(text)
        if m:
            findings.credential_hits.append(m.group(0).lower())

    return findings
