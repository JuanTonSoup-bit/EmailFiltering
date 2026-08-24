"""Gmail API client: list/fetch messages, parse them, and manage labels."""

from __future__ import annotations

import base64
from email.utils import parseaddr

from googleapiclient.discovery import build

import tldextract

from ..analysis.message import ParsedMessage
from ..config import settings
from .auth import get_credentials


def _domain_of(address: str) -> str:
    if "@" not in address:
        return ""
    host = address.rsplit("@", 1)[1].strip().lower()
    ext = tldextract.extract(host)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return host


def _b64url_decode(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode(
            "utf-8", errors="replace"
        )
    except Exception:
        return ""


class GmailClient:
    def __init__(self, interactive: bool = False) -> None:
        """Defaults to non-interactive: every programmatic caller (the poller,
        the /api/scan endpoint) runs inside a background server that must not
        pop a browser consent window. The one-time sign-in is a deliberate,
        separate step -- see app/gmail/auth.py."""
        creds = get_credentials(interactive=interactive)
        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self._label_cache: dict[str, str] = {}

    # -- Message listing / fetching --------------------------------------

    # Gmail's hard per-page maximum. Asking for more is silently capped.
    _PAGE_SIZE = 500

    def iter_message_ids(self, query: str, hard_limit: int = 2000):
        """Yield every message id matching `query`, following pagination.

        The single-page version this replaced was a real bug: it asked for the
        newest N ids and stopped. Once those N were scanned, every later cycle
        got the same N back, found them all already in the database, and
        reported "0 new" forever -- so anything older than the newest N was
        permanently unreachable, and a backlog could never be worked through.

        `hard_limit` is a safety bound, not a target: it stops a careless
        query (`in:anywhere` on a decade-old mailbox) from walking hundreds of
        pages. Callers decide how much of this stream to actually consume.
        """
        token = None
        seen = 0
        while True:
            request = {
                "userId": "me",
                "q": query,
                "maxResults": min(self._PAGE_SIZE, hard_limit - seen),
            }
            if token:
                request["pageToken"] = token

            resp = self.service.users().messages().list(**request).execute()

            for message in resp.get("messages", []):
                yield message["id"]
                seen += 1
                if seen >= hard_limit:
                    return

            token = resp.get("nextPageToken")
            if not token:
                return

    def list_message_ids(self, query: str, max_results: int) -> list[str]:
        """The first `max_results` ids matching `query`, across pages."""
        ids: list[str] = []
        for message_id in self.iter_message_ids(query, hard_limit=max_results):
            ids.append(message_id)
            if len(ids) >= max_results:
                break
        return ids

    def get_message(self, message_id: str) -> ParsedMessage:
        raw = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        return self._parse(raw)

    # -- Parsing ----------------------------------------------------------

    def _parse(self, raw: dict) -> ParsedMessage:
        payload = raw.get("payload", {})
        headers = {
            h["name"].lower(): h["value"] for h in payload.get("headers", [])
        }

        from_display, from_address = parseaddr(headers.get("from", ""))
        _, reply_to = parseaddr(headers.get("reply-to", ""))
        _, to_address = parseaddr(headers.get("to", ""))

        body_text, body_html = self._extract_bodies(payload)

        return ParsedMessage(
            gmail_id=raw.get("id", ""),
            thread_id=raw.get("threadId"),
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
            label_ids=raw.get("labelIds", []),
        )

    def _extract_bodies(self, payload: dict) -> tuple[str, str]:
        text_parts: list[str] = []
        html_parts: list[str] = []

        def walk(part: dict) -> None:
            mime = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")
            if data:
                decoded = _b64url_decode(data)
                if mime == "text/plain":
                    text_parts.append(decoded)
                elif mime == "text/html":
                    html_parts.append(decoded)
            for sub in part.get("parts", []) or []:
                walk(sub)

        walk(payload)
        return "\n".join(text_parts), "\n".join(html_parts)

    # -- Labels -----------------------------------------------------------

    def _labels(self) -> dict[str, str]:
        if self._label_cache:
            return self._label_cache
        resp = self.service.users().labels().list(userId="me").execute()
        self._label_cache = {
            lbl["name"]: lbl["id"] for lbl in resp.get("labels", [])
        }
        return self._label_cache

    def ensure_label(self, name: str) -> str:
        labels = self._labels()
        if name in labels:
            return labels[name]
        created = (
            self.service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._label_cache[name] = created["id"]
        return created["id"]

    def apply_label(self, message_id: str, label_name: str) -> None:
        label_id = self.ensure_label(label_name)
        self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()
