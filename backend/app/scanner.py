"""Scan orchestration: fetch new mail, analyze it, persist, and label."""

from __future__ import annotations

import logging

from sqlalchemy import select

from .analysis import analyze
from .config import settings
from .db import SessionLocal
from .gmail import GmailClient
from .models import ScannedEmail

log = logging.getLogger("phishguard.scanner")


class Scanner:
    def __init__(self, client: GmailClient | None = None) -> None:
        self.client = client or GmailClient()

    def _already_scanned(self, session, gmail_id: str) -> bool:
        return session.scalar(
            select(ScannedEmail.id).where(ScannedEmail.gmail_id == gmail_id)
        ) is not None

    def scan_once(self) -> dict:
        """Run one scan cycle. Returns a summary of what happened."""
        query = f"in:inbox newer_than:{settings.initial_lookback_days}d"
        ids = self.client.list_message_ids(query, settings.poll_max_results)

        scanned = 0
        flagged = 0
        summary_verdicts: dict[str, int] = {}

        with SessionLocal() as session:
            for gmail_id in ids:
                if self._already_scanned(session, gmail_id):
                    continue

                msg = self.client.get_message(gmail_id)
                result = analyze(msg)

                label_applied = None
                if result.verdict == "suspicious":
                    label_applied = settings.label_suspicious
                elif result.verdict == "junk":
                    label_applied = settings.label_junk

                if label_applied:
                    try:
                        self.client.apply_label(gmail_id, label_applied)
                        flagged += 1
                    except Exception:  # labeling must not lose the scan record
                        log.exception("Failed to apply label to %s", gmail_id)
                        label_applied = None

                session.add(
                    ScannedEmail(
                        gmail_id=gmail_id,
                        thread_id=msg.thread_id,
                        from_address=msg.from_address,
                        from_display=msg.from_display,
                        from_domain=msg.from_domain,
                        reply_to=msg.reply_to,
                        subject=msg.subject[:2000] if msg.subject else None,
                        date_sent=msg.date_sent,
                        spf=result.spf,
                        dkim=result.dkim,
                        dmarc=result.dmarc,
                        score=result.score,
                        verdict=result.verdict,
                        findings=result.findings_dict,
                        label_applied=label_applied,
                    )
                )
                session.commit()

                scanned += 1
                summary_verdicts[result.verdict] = (
                    summary_verdicts.get(result.verdict, 0) + 1
                )

        log.info("Scan complete: %d new, %d flagged", scanned, flagged)
        return {
            "scanned": scanned,
            "flagged": flagged,
            "verdicts": summary_verdicts,
        }
