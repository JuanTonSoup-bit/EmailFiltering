"""SQLAlchemy models for scanned emails and detection findings."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class ScannedEmail(Base):
    """One row per Gmail message PhishGuard has analyzed."""

    __tablename__ = "scanned_emails"
    __table_args__ = (UniqueConstraint("gmail_id", name="uq_scanned_gmail_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_id: Mapped[str] = mapped_column(String(64), index=True)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Envelope / display info
    from_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    from_display: Mapped[str | None] = mapped_column(String(320), nullable=True)
    from_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_sent: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Email authentication results (pass / fail / neutral / none / unknown)
    spf: Mapped[str | None] = mapped_column(String(16), nullable=True)
    dkim: Mapped[str | None] = mapped_column(String(16), nullable=True)
    dmarc: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Scoring / verdict
    score: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(16), default="clean", index=True)
    # findings: list of {code, label, weight, detail}
    findings: Mapped[list] = mapped_column(JSON, default=list)

    # Action taken in Gmail
    label_applied: Mapped[str | None] = mapped_column(String(64), nullable=True)

    scanned_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
