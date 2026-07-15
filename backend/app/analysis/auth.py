"""Parse email authentication results (SPF / DKIM / DMARC).

Gmail runs SPF/DKIM/DMARC on inbound mail and records the outcome in the
`Authentication-Results` header, so we read the verdict rather than re-running
the checks ourselves. Example header value:

    mx.google.com;
    spf=pass (google.com: domain of ...) smtp.mailfrom=news@example.com;
    dkim=pass header.i=@example.com;
    dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=example.com
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .message import ParsedMessage

# result token immediately following e.g. "spf=" up to whitespace
_MECH_RE = {
    "spf": re.compile(r"\bspf=(\w+)", re.IGNORECASE),
    "dkim": re.compile(r"\bdkim=(\w+)", re.IGNORECASE),
    "dmarc": re.compile(r"\bdmarc=(\w+)", re.IGNORECASE),
}

# Normalize the many SPF/DKIM/DMARC result keywords into three buckets.
_PASS = {"pass"}
_FAIL = {"fail", "softfail", "permerror", "reject", "quarantine"}


@dataclass
class AuthResults:
    spf: str = "unknown"
    dkim: str = "unknown"
    dmarc: str = "unknown"

    def bucket(self, value: str) -> str:
        v = value.lower()
        if v in _PASS:
            return "pass"
        if v in _FAIL:
            return "fail"
        return "other"


def parse_auth_results(msg: ParsedMessage) -> AuthResults:
    # Prefer Authentication-Results; fall back to ARC results.
    raw = msg.header("authentication-results")
    if not raw:
        raw = msg.header("arc-authentication-results")

    results = AuthResults()
    if not raw:
        return results

    for mech, pattern in _MECH_RE.items():
        match = pattern.search(raw)
        if match:
            setattr(results, mech, match.group(1).lower())
    return results
