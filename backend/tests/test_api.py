"""End-to-end tests for the HTTP API.

These exercise the real FastAPI app through Starlette's TestClient - real
routing, real dependency injection, real Pydantic serialisation - against the
throwaway database configured in conftest.py.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import ScannedEmail


@pytest.fixture()
def client() -> TestClient:
    init_db()
    with SessionLocal() as session:
        session.query(ScannedEmail).delete()
        session.commit()
    # The context manager runs the lifespan, which is what creates tables and
    # starts the poller. The poller cannot reach Gmail here (conftest points
    # the credentials at a nonexistent file) and is written to log and keep
    # going rather than take the app down with it - which is precisely the
    # behaviour worth having under test.
    with TestClient(app) as test_client:
        yield test_client


def seed(**overrides) -> None:
    when = dt.datetime.now(dt.timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    ) - dt.timedelta(days=overrides.pop("days_ago", 0))
    fields = dict(
        gmail_id=overrides.pop("gmail_id", "abc123"),
        from_address="sender@example.com",
        from_domain="example.com",
        subject="Your account needs attention",
        spf="pass",
        dkim="pass",
        dmarc="pass",
        score=0,
        verdict="clean",
        findings=[],
        scanned_at=when,
    )
    fields.update(overrides)
    with SessionLocal() as session:
        session.add(ScannedEmail(**fields))
        session.commit()


def test_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stats_shape(client: TestClient):
    seed(verdict="suspicious", score=75, gmail_id="s1")
    response = client.get("/api/stats?days=14")

    assert response.status_code == 200
    body = response.json()
    assert body["total_scanned"] == 1
    assert body["suspicious"] == 1
    # Every key the dashboard reads must be present even when empty, so the
    # front end never has to guard against a missing field.
    for key in ("verdicts", "auth_rates", "timeline", "top_senders"):
        assert key in body


def test_stats_rejects_out_of_range_days(client: TestClient):
    assert client.get("/api/stats?days=0").status_code == 422
    assert client.get("/api/stats?days=500").status_code == 422


def test_emails_filter_by_verdict(client: TestClient):
    seed(gmail_id="clean1", verdict="clean")
    seed(gmail_id="junk1", verdict="junk", score=30)

    everything = client.get("/api/emails").json()
    assert len(everything) == 2

    junk_only = client.get("/api/emails?verdict=junk").json()
    assert [e["gmail_id"] for e in junk_only] == ["junk1"]


def test_emails_rejects_unknown_verdict(client: TestClient):
    assert client.get("/api/emails?verdict=spam").status_code == 422


def test_emails_days_window(client: TestClient):
    seed(gmail_id="recent", days_ago=1)
    seed(gmail_id="ancient", days_ago=45)

    assert len(client.get("/api/emails").json()) == 2
    recent = client.get("/api/emails?days=7").json()
    assert [e["gmail_id"] for e in recent] == ["recent"]


def test_emails_newest_first(client: TestClient):
    seed(gmail_id="older", days_ago=3)
    seed(gmail_id="newer", days_ago=0)

    order = [e["gmail_id"] for e in client.get("/api/emails").json()]
    assert order == ["newer", "older"]


def test_email_detail_includes_findings(client: TestClient):
    seed(
        gmail_id="detail1",
        verdict="suspicious",
        score=75,
        findings=[
            {
                "code": "dmarc_fail",
                "label": "DMARC failed",
                "weight": 30,
                "detail": "DMARC result: fail",
            }
        ],
    )
    listed = client.get("/api/emails").json()
    response = client.get(f"/api/emails/{listed[0]['id']}")

    assert response.status_code == 200
    findings = response.json()["findings"]
    assert findings[0]["code"] == "dmarc_fail"
    assert findings[0]["weight"] == 30


def test_missing_email_is_404(client: TestClient):
    response = client.get("/api/emails/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Email not found"


def test_scan_without_credentials_fails_loudly_but_does_not_kill_the_app(
    client: TestClient,
):
    """A manual scan with no OAuth client secret should return an error, and
    the rest of the API must keep working afterwards."""
    with pytest.raises(FileNotFoundError):
        client.post("/api/scan", headers={"X-PhishGuard-Client": "test"})

    assert client.get("/api/health").status_code == 200


# --- Unattended contexts must never open a browser -------------------------

def test_gmail_client_defaults_to_non_interactive():
    """The poller and /api/scan construct GmailClient() with no arguments.
    If that default ever flips to interactive, a logon-started server would
    pop an OAuth consent window at every sign-in."""
    import inspect

    from app.gmail.client import GmailClient

    default = inspect.signature(GmailClient.__init__).parameters["interactive"].default
    assert default is False


def test_non_interactive_auth_raises_actionable_error(monkeypatch):
    from app.gmail import auth

    # No token file, no chance of refreshing: the unattended path must raise
    # rather than reach InstalledAppFlow.
    monkeypatch.setattr(auth.settings, "gmail_token_file", "definitely-not-here.json")
    # A client secret that DOES exist, so we get past the missing-credentials
    # branch and reach the interactive/non-interactive decision.
    monkeypatch.setattr(auth.os.path, "exists", lambda p: p != "definitely-not-here.json")

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("interactive OAuth flow was started unattended")

    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_secrets_file", explode)

    with pytest.raises(RuntimeError) as excinfo:
        auth.get_credentials(interactive=False)

    # The message has to tell you what to actually do about it.
    assert "get_credentials" in str(excinfo.value)


# --- State-changing endpoints are protected from cross-site requests -------
# Without the header requirement, any web page you visited could POST to your
# local API: triggering scans, or silently shutting the filter off.

def test_scan_requires_client_header(client: TestClient):
    response = client.post("/api/scan")
    assert response.status_code == 403
    assert "X-PhishGuard-Client" in response.json()["detail"]


def test_shutdown_requires_client_header(client: TestClient):
    response = client.post("/api/shutdown")
    assert response.status_code == 403
    # The guard must run BEFORE the handler - a rejected request must not have
    # scheduled a shutdown.
    assert client.get("/api/health").status_code == 200


def test_shutdown_accepts_request_with_header(client: TestClient, monkeypatch):
    """With the header present the endpoint accepts and schedules shutdown.
    The actual exit is stubbed - a real one would kill the test run."""
    from app import main

    scheduled = {}

    def fake_shutdown(delay: float = 0.25):
        scheduled["called"] = True

        async def noop():
            return None

        return noop()

    monkeypatch.setattr(main, "_shutdown_soon", fake_shutdown)

    response = client.post(
        "/api/shutdown", headers={"X-PhishGuard-Client": "test"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "stopping"}
    assert scheduled.get("called") is True


def test_read_endpoints_do_not_require_the_header(client: TestClient):
    """The guard is for writes only. Reads staying open keeps curl, scripts,
    and the browser's address bar usable."""
    for path in ("/api/health", "/api/stats?days=7", "/api/emails"):
        assert client.get(path).status_code == 200
