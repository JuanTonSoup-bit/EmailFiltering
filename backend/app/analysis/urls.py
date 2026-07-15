"""URL extraction and heuristic risk analysis."""

from __future__ import annotations

import html
import ipaddress
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import tldextract

# Extract href + visible anchor text from HTML bodies.
_ANCHOR_RE = re.compile(
    r'<a\s[^>]*href=["\']?(?P<href>[^"\'>\s]+)["\']?[^>]*>(?P<text>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
# Bare URLs anywhere in text.
_URL_RE = re.compile(r'https?://[^\s"\'<>)]+', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")

# Common link shorteners abused to hide destinations.
SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly",
    "rebrand.ly", "cutt.ly", "shorturl.at", "rb.gy", "t.ly",
}


def _registered_domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    ext = tldextract.extract(host)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}".lower()
    return host.lower()


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_ip_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


@dataclass
class UrlFindings:
    total_links: int = 0
    mismatched_anchors: list[tuple[str, str]] = field(default_factory=list)
    ip_links: list[str] = field(default_factory=list)
    shortener_links: list[str] = field(default_factory=list)
    domains: set[str] = field(default_factory=set)


def analyze_urls(body_text: str, body_html: str) -> UrlFindings:
    findings = UrlFindings()
    seen: set[str] = set()

    # Anchor tags: compare where the text *claims* to point vs. the real href.
    for match in _ANCHOR_RE.finditer(body_html or ""):
        href = html.unescape(match.group("href").strip())
        if not href.lower().startswith("http"):
            continue
        text = _TAG_RE.sub("", match.group("text"))
        text = html.unescape(text).strip()

        seen.add(href)
        href_domain = _registered_domain(href)
        if href_domain:
            findings.domains.add(href_domain)

        # If the anchor text itself looks like a URL/domain, it should match.
        text_url = _URL_RE.search(text)
        if text_url:
            claimed = _registered_domain(text_url.group(0))
            if claimed and href_domain and claimed != href_domain:
                findings.mismatched_anchors.append((claimed, href_domain))

    # All URLs (anchors + bare) for IP / shortener checks.
    all_urls = set(seen)
    all_urls.update(_URL_RE.findall(body_html or ""))
    all_urls.update(_URL_RE.findall(body_text or ""))

    findings.total_links = len(all_urls)
    for url in all_urls:
        host = _host(url)
        domain = _registered_domain(url)
        if domain:
            findings.domains.add(domain)
        if host and _is_ip_host(host):
            findings.ip_links.append(url)
        if domain in SHORTENERS:
            findings.shortener_links.append(url)

    return findings
