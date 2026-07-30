"""Scoring engine: combine analyzer findings into an explainable verdict.

Each detected signal contributes weighted points and a human-readable reason.
The total score maps to a verdict via configurable thresholds:

    score >= suspicious_threshold  -> "suspicious" (likely phishing)
    score >= junk_threshold        -> "junk"       (spam / bulk)
    otherwise                      -> "clean"

Every finding is retained so the dashboard can explain *why* mail was flagged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import settings
from .auth import parse_auth_results
from .language import analyze_language
from .message import ParsedMessage
from .spoofing import analyze_spoofing
from .typosquat import check_domain
from .urls import analyze_urls


@dataclass
class Finding:
    code: str
    label: str
    weight: int
    detail: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "label": self.label,
            "weight": self.weight,
            "detail": self.detail,
        }


@dataclass
class AnalysisResult:
    score: int
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    spf: str = "unknown"
    dkim: str = "unknown"
    dmarc: str = "unknown"

    @property
    def findings_dict(self) -> list[dict]:
        return [f.as_dict() for f in self.findings]


def _has_unsubscribe(msg: ParsedMessage) -> bool:
    return bool(msg.header("list-unsubscribe") or msg.header("list-id"))


def analyze(msg: ParsedMessage) -> AnalysisResult:
    findings: list[Finding] = []
    score = 0

    def add(code: str, label: str, weight: int, detail: str) -> None:
        nonlocal score
        findings.append(Finding(code, label, weight, detail))
        score += weight

    # --- Email authentication -------------------------------------------
    auth = parse_auth_results(msg)
    if auth.bucket(auth.dmarc) == "fail":
        add("dmarc_fail", "DMARC failed", 30,
            f"DMARC result: {auth.dmarc}")
    if auth.bucket(auth.spf) == "fail":
        add("spf_fail", "SPF failed", 15, f"SPF result: {auth.spf}")
    if auth.bucket(auth.dkim) == "fail":
        add("dkim_fail", "DKIM failed", 15, f"DKIM result: {auth.dkim}")

    # --- Sender spoofing -------------------------------------------------
    spoof = analyze_spoofing(msg)
    if spoof.display_name_spoof:
        add("display_name_spoof", "Brand impersonation in sender name", 30,
            spoof.display_name_spoof)
    if spoof.display_email_mismatch:
        add("display_email_mismatch", "Sender name shows a different address",
            20, spoof.display_email_mismatch)
    if spoof.reply_to_mismatch:
        add("reply_to_mismatch", "Reply-To domain differs from From", 15,
            spoof.reply_to_mismatch)

    # --- URLs ------------------------------------------------------------
    urls = analyze_urls(msg.body_text, msg.body_html)
    if urls.mismatched_anchors:
        claimed, actual = urls.mismatched_anchors[0]
        add("url_mismatch", "Link text hides a different destination", 25,
            f"shows {claimed}, links to {actual}")
    if urls.ip_links:
        add("ip_url", "Link points to a raw IP address", 20,
            urls.ip_links[0])
    if urls.shortener_links:
        add("url_shortener", "Uses a link shortener", 10,
            urls.shortener_links[0])

    # --- Domain typosquatting (sender + links) ---------------------------
    # The dedicated detector (homoglyph / typo / combo / TLD-swap) supersedes
    # spoofing.py's simpler lookalike check for the sender domain; fall back
    # to it only when the detector finds nothing.
    sender_squat = check_domain(msg.from_domain) if msg.from_domain else None
    if sender_squat:
        add("typosquat_domain", "Sender domain impersonates a brand", 30,
            sender_squat.describe())
    elif spoof.lookalike_brand:
        add("lookalike_domain", "Lookalike sender domain", 30,
            spoof.lookalike_brand)

    for link_domain in sorted(urls.domains):
        if link_domain == msg.from_domain:
            continue
        link_squat = check_domain(link_domain)
        if link_squat:
            add("typosquat_link", "Link domain impersonates a brand", 25,
                link_squat.describe())
            break

    # --- Language --------------------------------------------------------
    lang = analyze_language(msg.subject, msg.body_text)
    if lang.credential_hits:
        add("credential_request", "Requests credentials / account action", 20,
            "; ".join(lang.credential_hits[:3]))
    if lang.urgency_hits:
        add("urgency", "Urgency / pressure language", 10,
            "; ".join(lang.urgency_hits[:3]))

    # --- Bulk / junk signal ---------------------------------------------
    # Marketing bulk mail is not phishing but is junk. Small weight so it
    # tips borderline mail into "junk" without ever reaching "suspicious".
    if _has_unsubscribe(msg):
        add("bulk_mail", "Bulk / mailing-list message", 12,
            "List-Unsubscribe / List-Id header present")

    score = min(score, 100)

    if score >= settings.suspicious_threshold:
        verdict = "suspicious"
    elif score >= settings.junk_threshold:
        verdict = "junk"
    else:
        verdict = "clean"

    return AnalysisResult(
        score=score,
        verdict=verdict,
        findings=findings,
        spf=auth.spf,
        dkim=auth.dkim,
        dmarc=auth.dmarc,
    )
