# Setup

Getting PhishGuard running, from a fresh clone.

There are **two paths**. Pick the one that matches what you want right now.

- **[Path A — Demo mode](#path-a--demo-mode-5-minutes)**: see the dashboard
  working immediately, with realistic generated data. No Google account, no
  OAuth, no credentials. ~5 minutes.
- **[Path B — Live Gmail](#path-b--live-gmail)**: connect it to your real
  inbox. Adds the Google Cloud OAuth setup. ~15 minutes, most of it clicking
  through the Google Cloud Console once.

Do Path A first even if you want Path B. It confirms the whole stack works
before OAuth is in the picture, so if something goes wrong later you know it
is the Google side.

---

## Prerequisites

| | Version | Check with |
|---|---|---|
| Python | 3.11+ (3.14 tested) | `python --version` |
| Node.js | 18+ (24 tested) | `node --version` |
| npm | 9+ | `npm --version` |

---

## Path A — Demo mode (5 minutes)

### 1. Backend dependencies

```bash
cd backend
python -m venv .venv
```

Activate it:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```
```bash
# macOS / Linux
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
pip install pytest httpx      # only needed to run the test suite
cp .env.example .env
```

> **If pip tries to compile `pydantic-core` from Rust source and fails**, your
> pydantic pin is too old for your Python version. `requirements.txt` already
> requires `pydantic>=2.11.7`, the first release with prebuilt wheels for
> Python 3.14. Make sure you installed from that file rather than an older
> lockfile.

### 2. Generate demo data

```bash
python -m app.tools.seed_demo --count 160 --days 21
```

```
Seeded 160 messages across 21 days:
  clean       122
  junk        28
  suspicious  10
```

These are synthetic messages run through the **real** detection engine — the
scores and findings are the ones the engine actually produces, not hard-coded
values.

### 3. Build the dashboard

```bash
cd ../frontend
npm install
npm run build
```

### 4. Run it

```bash
cd ../backend
uvicorn app.main:app --port 8000
```

Open **http://localhost:8000/**.

You will see one warning in the log about missing Gmail credentials. That is
expected in demo mode — the poller logs it, retries later, and never takes the
app down.

---

## Path B — Live Gmail

Complete Path A first, then add the OAuth credentials below.

### 1. Create a Google Cloud project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project — call it `phishguard`.

### 2. Enable the Gmail API

**APIs & Services → Library → Gmail API → Enable.**

### 3. Configure the consent screen

**APIs & Services → OAuth consent screen:**

- User type: **External**
- Fill in the app name and your email where required
- On the **Test users** step, **add your own Gmail address**

Adding yourself as a test user is what keeps the app in *testing* mode, which
means no Google verification review. Testing-mode refresh tokens expire after
7 days — if scanning silently stops after a week, delete `backend/token.json`
and restart to sign in again. (Publishing the app removes that expiry but
triggers a verification review, which is not worth it for a personal tool.)

### 4. Create the OAuth client

**APIs & Services → Credentials → Create Credentials → OAuth client ID →
Application type: Desktop app.**

Download the JSON and save it as **`backend/credentials.json`**.

It must be a **Desktop app** client. A Web application client uses a different
redirect flow and `InstalledAppFlow` will reject it.

> `credentials.json` and `token.json` are both in `.gitignore`.
> **`token.json` is a live credential to your mailbox** — treat it like a
> password. If it leaks, revoke access at
> [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

### 5. First run

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

A browser window opens asking you to authorise the app. You will see an
"unverified app" warning — that is expected for a testing-mode app; click
through it. After consenting, `token.json` is written and **you will not be
asked again**.

### 6. Clear the demo data (optional but recommended)

```bash
python -c "from app.db import SessionLocal; from app.models import ScannedEmail; s=SessionLocal(); print(s.query(ScannedEmail).delete()); s.commit()"
```

Or just delete `backend/data/phishguard.db` and restart.

### 7. Scan

The poller runs every `POLL_INTERVAL_SECONDS` (default 120). To scan
immediately, press **Scan now** in the dashboard, or:

```bash
curl -X POST http://localhost:8000/api/scan
```

First run scans mail from the last `INITIAL_LOOKBACK_DAYS` days (default 3),
up to `POLL_MAX_RESULTS` messages (default 25).

Check Gmail: flagged messages now carry a `PhishGuard/Suspicious` or
`PhishGuard/Junk` label, still sitting in the inbox.

---

## Development mode

For working on the frontend, run the two servers separately so you get hot
reload:

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Then use **http://localhost:5173/** (not :8000). Vite proxies `/api` to the
backend, so there is no CORS involved and the code path is identical to
production.

---

## Configuration

Everything lives in `backend/.env`. Restart the server after changing it.

| Variable | Default | What it does |
|---|---|---|
| `SUSPICIOUS_THRESHOLD` | `50` | Score at or above this → `PhishGuard/Suspicious` |
| `JUNK_THRESHOLD` | `25` | Score at or above this → `PhishGuard/Junk` |
| `POLL_INTERVAL_SECONDS` | `120` | How often the inbox is checked |
| `POLL_MAX_RESULTS` | `25` | Max messages fetched per cycle |
| `INITIAL_LOOKBACK_DAYS` | `3` | How far back the Gmail query reaches |
| `LABEL_SUSPICIOUS` | `PhishGuard/Suspicious` | Label for likely phishing |
| `LABEL_JUNK` | `PhishGuard/Junk` | Label for bulk/spam |
| `DATABASE_URL` | `sqlite:///./data/phishguard.db` | Any SQLAlchemy URL |
| `GMAIL_CREDENTIALS_FILE` | `credentials.json` | OAuth client secret path |
| `GMAIL_TOKEN_FILE` | `token.json` | Cached token path |

See [DETECTION.md](DETECTION.md#part-4--tuning-it) for how to tune the
thresholds against real results.

---

## Verifying the install

```bash
cd backend
pytest -q
```

Expect **36 passed**. No test touches the network or your real database.

Offline detection check, no credentials needed:

```bash
python -m app.tools.scan_eml samples/phish_paypal.eml
python -m app.tools.scan_eml --domain paypa1-secure.com
```

---

## Troubleshooting

**The dashboard says "Can't reach the PhishGuard API".**
uvicorn is not running, or it is on a different port. Start it and the page
reconnects on its own — it re-probes every 30 seconds.

**The page loads but says "No mail scanned yet".**
The backend is fine and the database is empty. Either seed demo data (Path A
step 2) or complete OAuth and press **Scan now**.

**`FileNotFoundError: Missing OAuth client secret at 'credentials.json'`.**
Path B step 4 is incomplete, or the file is not in `backend/` — the path is
relative to the directory uvicorn was started from.

**Scanning worked, then stopped after about a week.**
Testing-mode refresh tokens expire after 7 days. Delete `backend/token.json`
and restart to sign in again.

**`http://localhost:8000/` returns 404.**
The frontend has not been built. Run `npm run build` in `frontend/` — FastAPI
only mounts the static files if `frontend/dist` exists.

**Labels are not appearing in Gmail.**
Check the log for "Failed to apply label". Labelling failures are caught and
logged so the analysis is never lost; the dashboard shows those rows with no
label applied.

**`RuntimeError: ... is bound to a different event loop`.**
This was a real bug in `poller.py`, fixed by creating the stop `Event` inside
`start()` rather than at import time. If you see it, your copy predates that
fix.

---

## A word on exposure

**The API has no authentication.** It is designed to bind to localhost on a
machine you control.

Do not put it on a public address. Anyone who can reach it can read every
subject line, sender, and finding in your mailbox history, and can trigger
scans. If you want it on another device, use a VPN or an SSH tunnel — not a
port forward:

```bash
ssh -L 8000:localhost:8000 you@your-server
```

Adding real authentication would mean a login flow, sessions or tokens, and
CSRF protection on the one POST endpoint. That is a reasonable v2 feature; it
is not something to approximate with a hardcoded password.
