"""Structured representation of an email, decoupled from the Gmail API format."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedMessage:
    """Everything the analysis engine needs, extracted from a raw message."""

    gmail_id: str
    thread_id: str | None
    headers: dict[str, str]  # lower-cased header name -> value
    subject: str
    from_address: str
    from_display: str
    from_domain: str
    reply_to: str
    reply_to_domain: str
    to_address: str
    date_sent: str
    body_text: str
    body_html: str
    label_ids: list[str] = field(default_factory=list)

    def header(self, name: str) -> str:
        return self.headers.get(name.lower(), "")
