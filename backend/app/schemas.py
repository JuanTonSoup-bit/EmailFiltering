"""Pydantic response models for the API."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class Finding(BaseModel):
    code: str
    label: str
    weight: int
    detail: str


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gmail_id: str
    from_address: str | None
    from_display: str | None
    from_domain: str | None
    reply_to: str | None
    subject: str | None
    date_sent: str | None
    spf: str | None
    dkim: str | None
    dmarc: str | None
    score: int
    verdict: str
    findings: list[Finding]
    label_applied: str | None
    scanned_at: dt.datetime


class VerdictCount(BaseModel):
    verdict: str
    count: int


class AuthRate(BaseModel):
    mechanism: str  # spf | dkim | dmarc
    passed: int
    failed: int
    other: int


class TimePoint(BaseModel):
    date: str  # YYYY-MM-DD
    clean: int
    junk: int
    suspicious: int


class TopSender(BaseModel):
    from_domain: str
    count: int
    max_score: int


class DashboardStats(BaseModel):
    total_scanned: int
    total_flagged: int
    suspicious: int
    junk: int
    clean: int
    verdicts: list[VerdictCount]
    auth_rates: list[AuthRate]
    timeline: list[TimePoint]
    top_senders: list[TopSender]
