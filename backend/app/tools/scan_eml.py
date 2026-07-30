"""Scan a raw .eml file, or check a single domain, with the PhishGuard engine.

Runs entirely offline - no Gmail OAuth required - so it is handy for testing,
demos, and triaging a suspicious message someone forwarded as a .eml file.

Usage:
    python -m app.tools.scan_eml message.eml
    python -m app.tools.scan_eml --domain paypa1-secure.com
"""

from __future__ import annotations

import argparse
import sys

from app.analysis import analyze
from app.analysis.eml import parse_eml_file
from app.analysis.typosquat import check_domain


def _scan_file(path: str) -> int:
    try:
        msg = parse_eml_file(path)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    result = analyze(msg)

    print(f"File:    {path}")
    print(f"From:    {msg.from_display} <{msg.from_address}>")
    print(f"Domain:  {msg.from_domain or '(none)'}")
    print(f"Subject: {msg.subject}")
    print(f"Auth:    SPF={result.spf}  DKIM={result.dkim}  DMARC={result.dmarc}")
    print(f"Verdict: {result.verdict.upper()}  (score {result.score}/100)")
    if result.findings:
        print("Findings:")
        for f in result.findings:
            print(f"  [{f.weight:>2}] {f.label}: {f.detail}")
    else:
        print("Findings: none")
    return 0


def _check_domain(domain: str) -> int:
    hit = check_domain(domain)
    if hit is None:
        print(f"{domain}: no brand impersonation detected")
        return 0
    print(
        f"{domain}: TYPOSQUAT of '{hit.brand}' "
        f"via {hit.technique} (confidence {hit.confidence:.0%})"
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scan_eml", description="Scan a .eml file or check a domain for typosquatting."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("eml", nargs="?", help="path to a .eml file to scan")
    group.add_argument("--domain", help="check a single domain for typosquatting")
    args = parser.parse_args(argv)

    if args.domain:
        return _check_domain(args.domain)
    return _scan_file(args.eml)


if __name__ == "__main__":
    raise SystemExit(main())
