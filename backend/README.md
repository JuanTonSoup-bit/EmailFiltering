# PhishGuard backend

FastAPI service: Gmail integration, detection engine, background poller, and the
dashboard API.

> **In a hurry, or don't want to set up OAuth yet?** Skip to
> [Demo mode](#demo-mode-no-google-account) — it fills the database with
> realistic data scored by the real engine, so you can run the whole stack in
> about five minutes with no Google account.
>
> **Full write-up** of what FastAPI, SQLAlchemy, Pydantic and uvicorn each do
> and why they were chosen, plus a file-by-file tour, is in
> [`../docs/BACKEND.md`](../docs/BACKEND.md).

## Prerequisites

- Python 3.11+ (3.14 tested)
- A Google account (Gmail) — only for live scanning

## 1. Enable the Gmail API and get OAuth credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (e.g. `phishguard`).
3. **APIs & Services -> Library -> Gmail API -> Enable.**
4. **APIs & Services -> OAuth consent screen:** choose *External*, add yourself
   as a **Test user** (this keeps the app in testing mode, no verification
   needed).
5. **APIs & Services -> Credentials -> Create Credentials -> OAuth client ID ->
   Desktop app.** Download the JSON.
6. Save it as `backend/credentials.json` (git-ignored).

The requested scope is `gmail.modify` — read messages and add labels. PhishGuard
never sends, deletes, or permanently removes mail.

## 2. Install and configure

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # adjust thresholds / labels if desired
```

## 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

- On first run a browser opens for Google consent; a `token.json` is cached.
- The poller scans your inbox every `POLL_INTERVAL_SECONDS`.
- Trigger a scan immediately: `curl -X POST http://localhost:8000/api/scan`
- API docs: http://localhost:8000/docs

## API

| Method | Path                | Description                         |
|--------|---------------------|-------------------------------------|
| GET    | `/api/health`       | Liveness check                      |
| GET    | `/api/stats?days=14`| Dashboard aggregates (1–90 days)    |
| GET    | `/api/emails`       | Scanned emails — `verdict`, `days`, `limit`, `offset` |
| GET    | `/api/emails/{id}`  | One email with findings             |
| POST   | `/api/scan`         | Run a scan cycle now                |

`days` uses the same calendar-day window on both `/api/stats` and
`/api/emails`, anchored to midnight UTC, so every figure the dashboard shows
comes from one identical slice of the data.

## Demo mode (no Google account)

`app/tools/seed_demo.py` fills the database with a realistic inbox mix so the
dashboard can be run and reviewed before any OAuth setup:

```bash
python -m app.tools.seed_demo --count 160 --days 21
python -m app.tools.seed_demo --reset          # wipe first
python -m app.tools.seed_demo --seed 7         # repeatable data
```

Nothing in it hard-codes a verdict — every row is a synthetic message run
through the real `analyze()` function, so if a weight changes in `engine.py`
the demo data changes with it.

## Offline scanning (no Gmail account needed)

The detection engine also runs on raw `.eml` files, so you can triage a
forwarded message or check a domain without connecting a mailbox:

```bash
# Full analysis of a saved email
python -m app.tools.scan_eml samples/phish_paypal.eml

# Just check one domain for typosquatting
python -m app.tools.scan_eml --domain paypa1-secure.com
```

The typosquatting detector (`app/analysis/typosquat.py`) flags sender and link
domains that impersonate known brands via homoglyph swaps (`paypa1.com`), small
typos (`micrsoft.com`), combosquatting (`paypal-secure-login.com`), or TLD
swaps (`paypal.co`).

## Tests

```bash
pip install pytest httpx
pytest -q
```

36 tests covering the scoring engine and each analyzer, typosquat
classification, `.eml` parsing, every dashboard aggregate, and every API
endpoint including its failure modes. `tests/conftest.py` redirects
`DATABASE_URL` to a temp file before any app module is imported, so a test run
can never read or write your real `data/phishguard.db`.

## How scoring works

Each analyzer contributes weighted, human-readable findings; the total maps to a
verdict (`clean` / `junk` / `suspicious`) via thresholds in `.env`. See
`app/analysis/engine.py`. Every finding is stored so the dashboard can explain
*why* a message was flagged.

Every signal, its weight, the reasoning behind it, and how to tune the
thresholds against real results: [`../docs/DETECTION.md`](../docs/DETECTION.md).
