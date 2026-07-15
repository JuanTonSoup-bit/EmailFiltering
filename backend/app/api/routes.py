"""HTTP routes for the dashboard and manual controls."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import ScannedEmail
from ..schemas import DashboardStats, EmailOut
from ..stats import build_dashboard

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/stats", response_model=DashboardStats)
def stats(
    days: int = Query(14, ge=1, le=90),
    session: Session = Depends(get_session),
) -> DashboardStats:
    return build_dashboard(session, days=days)


@router.get("/emails", response_model=list[EmailOut])
def list_emails(
    verdict: str | None = Query(None, pattern="^(clean|junk|suspicious)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> list[ScannedEmail]:
    stmt = select(ScannedEmail).order_by(ScannedEmail.scanned_at.desc())
    if verdict:
        stmt = stmt.where(ScannedEmail.verdict == verdict)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.scalars(stmt).all())


@router.get("/emails/{email_id}", response_model=EmailOut)
def get_email(
    email_id: int,
    session: Session = Depends(get_session),
) -> ScannedEmail:
    from fastapi import HTTPException

    email = session.get(ScannedEmail, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return email
