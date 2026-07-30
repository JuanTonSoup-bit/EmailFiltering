"""Parse a raw RFC 5322 / .eml message into a ParsedMessage.

The Gmail client builds ParsedMessage objects from the Gmail API JSON format.
This module builds the same structure from a raw email (bytes or the contents
of a .eml file), so the detection engine can run on any email source and be
tested offline with no OAuth credentials.
"""

from __future__ import annotations

import email
from email import policy
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

import tldextract

from .message import ParsedMessage


def _domain_of(address: str) -> str:
    if "@" not in address:
        return ""
    host = address.rsplit("@", 1)[1].strip().lower().rstrip(">")
    ext = tldextract.extract(host)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return host


def _extract_bodies(msg: EmailMessage) -> tuple[str, str]:
    text_parts: list[str] = []
    html_parts: list[str] = []

    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            content = part.get_content()
        except (LookupError, ValueError):
            # Unknown charset / undecodable part - fall back to raw payload.
            payload = part.get_payload(decode=True) or b""
            content = payload.decode("utf-8", errors="replace")
        if ctype == "text/plain":
            text_parts.append(content)
        else:
            html_parts.append(content)

    return "\n".join(text_parts), "\n".join(html_parts)


def parse_eml(raw: bytes | str, message_id: str = "") -> ParsedMessage:
    """Parse raw email bytes/text into a ParsedMessage."""
    if isinstance(raw, str):
        msg = email.message_from_string(raw, policy=policy.default)
    else:
        msg = email.message_from_bytes(raw, policy=policy.default)

    # Last value wins for repeated headers, matching the Gmail client's dict.
    headers = {k.lower(): str(v) for k, v in msg.items()}

    from_display, from_address = parseaddr(headers.get("from", ""))
    _, reply_to = parseaddr(headers.get("reply-to", ""))
    _, to_address = parseaddr(headers.get("to", ""))

    body_text, body_html = _extract_bodies(msg)

    return ParsedMessage(
        gmail_id=message_id or headers.get("message-id", ""),
        thread_id=None,
        headers=headers,
        subject=headers.get("subject", ""),
        from_address=from_address,
        from_display=from_display,
        from_domain=_domain_of(from_address),
        reply_to=reply_to,
        reply_to_domain=_domain_of(reply_to),
        to_address=to_address,
        date_sent=headers.get("date", ""),
        body_text=body_text,
        body_html=body_html,
        label_ids=[],
    )


def parse_eml_file(path: str | Path) -> ParsedMessage:
    """Parse a .eml file from disk into a ParsedMessage."""
    data = Path(path).read_bytes()
    return parse_eml(data, message_id=str(path))
