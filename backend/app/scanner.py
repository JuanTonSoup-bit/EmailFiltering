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
        """Run one scan cycle. Returns a summary of what happened.

        `poll_max_results` bounds the number of messages actually ANALYSED,
        not the number of ids fetched. That distinction is what lets a backlog
        drain: listing ids is cheap and paginated, so each cycle walks the
        window until it has found `poll_max_results` messages it has not seen
        before, then stops. Run it enough times and the whole window is
        covered; steady state is a handful of new messages per cycle.

        Capping the ID LIST instead -- the previous behaviour -- meant asking
        for the newest N every time and never seeing anything older.
        """
        query = f"in:inbox newer_than:{settings.initial_lookback_days}d"

        scanned = 0
        flagged = 0
        considered = 0
        summary_verdicts: dict[str, int] = {}

        with SessionLocal() as session:
            for gmail_id in self.client.iter_message_ids(query):
                considered += 1

                if self._already_scanned(session, gmail_id):
                    continue

                if scanned >= settings.poll_max_results:
                    # Budget spent. Whatever is left in the window is picked
                    # up next cycle. We deliberately do NOT report a
                    # "remaining" count: finding it would mean walking the
                    # rest of the window, which is the work we just chose to
                    # defer.
                    log.info(
                        "Reached per-cycle limit of %d new messages; more "
                        "remain in this window and will be scanned next cycle",
                        settings.poll_max_results,
                    )
                    break

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

        log.info(
            "Scan complete: %d new, %d flagged (%d ids considered)",
            scanned,
            flagged,
            considered,
        )
        return {
            "scanned": scanned,
            "flagged": flagged,
            "considered": considered,
            "verdicts": summary_verdicts,
        }
