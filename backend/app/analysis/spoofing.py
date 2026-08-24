"""Sender-spoofing and lookalike-domain heuristics."""

from __future__ import annotations

import re
from dataclasses import dataclass

import tldextract

from .message import ParsedMessage

# Well-known brands frequently impersonated in phishing, mapped to the
# domains they legitimately own. Used for display-name and lookalike checks.
#
# These sets must include FIRST-PARTY INFRASTRUCTURE domains, not just the
# domain a user would type. Real mail from Microsoft links to
# microsoftonline.com; real mail from Google links to googleusercontent.com.
# Both contain their brand as a token, so the combosquat rule flags them as
# impersonation unless they are listed here as legitimate.
#
# This was not hypothetical: the first live scan against a real inbox
# produced exactly two flags, and both were this false positive.
BRAND_DOMAINS: dict[str, set[str]] = {
    "paypal": {"paypal.com", "paypalobjects.com"},
    "microsoft": {
        "microsoft.com", "outlook.com", "office.com", "live.com",
        "microsoftonline.com", "microsoft365.com", "office365.com",
        "sharepoint.com", "onedrive.com", "azure.com", "windows.net",
        "azurewebsites.net", "msftauth.net", "skype.com", "msn.com",
    },
    "apple": {"apple.com", "icloud.com", "mzstatic.com"},
    "amazon": {
        "amazon.com", "amazonaws.com", "media-amazon.com",
        "ssl-images-amazon.com", "amazontrust.com",
    },
    "google": {
        "google.com", "gmail.com", "googleusercontent.com", "googleapis.com",
        "gstatic.com", "googlemail.com", "youtube.com", "withgoogle.com",
    },
    "netflix": {"netflix.com", "nflxext.com", "nflximg.net", "nflxvideo.net"},
    "chase": {"chase.com"},
    "wellsfargo": {"wellsfargo.com"},
    "bankofamerica": {"bankofamerica.com"},
    "docusign": {"docusign.com", "docusign.net"},
    "dhl": {"dhl.com"},
    "fedex": {"fedex.com"},
    "ups": {"ups.com"},
    "usps": {"usps.com"},
    "coinbase": {"coinbase.com"},
    "instagram": {"instagram.com", "cdninstagram.com"},
    "facebook": {"facebook.com", "fb.com", "fbcdn.net", "messenger.com"},
    "linkedin": {"linkedin.com", "licdn.com"},
}


def legitimate_brand(domain: str) -> str | None:
    """Return the brand that legitimately owns `domain`, or None.

    Used to recognise a brand's own infrastructure. The registrable domain is
    compared, so a subdomain like `login.microsoftonline.com` resolves to
    `microsoftonline.com` and matches.
    """
    if not domain:
        return None
    reg = _registered(domain)
    for brand, legit in BRAND_DOMAINS.items():
        if reg in legit:
            return brand
    return None

_EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@([\w.-]+\.\w+)")


@dataclass
class SpoofFindings:
    reply_to_mismatch: str | None = None  # "from vs reply-to"
    display_name_spoof: str | None = None  # brand impersonated in display name
    display_email_mismatch: str | None = None  # display shows a different address
    lookalike_brand: str | None = None  # from domain mimics a brand


def _registered(domain: str) -> str:
    ext = tldextract.extract(domain)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}".lower()
    return domain.lower()


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
            cur.append(
                min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            )
        prev = cur
    return prev[-1]


def analyze_spoofing(msg: ParsedMessage) -> SpoofFindings:
    findings = SpoofFindings()
    from_domain = _registered(msg.from_domain) if msg.from_domain else ""
    display = (msg.from_display or "").lower()

    # 1. Reply-To points to a different domain than From.
    if msg.reply_to_domain and from_domain:
        rt = _registered(msg.reply_to_domain)
        if rt and rt != from_domain:
            findings.reply_to_mismatch = f"{from_domain} -> {rt}"

    # 2. Display name embeds an email address for a different domain.
    m = _EMAIL_IN_TEXT.search(display)
    if m and from_domain:
        shown = _registered(m.group(1))
        if shown and shown != from_domain:
            findings.display_email_mismatch = f"shows {shown}, sent from {from_domain}"

    # 3. Display name claims a brand the sending domain doesn't own.
    for brand, legit in BRAND_DOMAINS.items():
        if brand in display and from_domain and from_domain not in legit:
            findings.display_name_spoof = f"'{brand}' but sent from {from_domain}"
            break

    # 4. From domain is a typosquat / lookalike of a known brand.
    if from_domain:
        label = from_domain.split(".")[0]
        for brand, legit in BRAND_DOMAINS.items():
            if from_domain in legit:
                break
            dist = _levenshtein(label, brand)
            # close but not equal, or brand embedded in a longer label
            if (0 < dist <= 2 and len(brand) >= 4) or (
                brand in label and label != brand and len(brand) >= 5
            ):
                findings.lookalike_brand = f"{from_domain} ~ {brand}"
                break

    return findings
