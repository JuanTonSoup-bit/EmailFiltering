# Architecture

How PhishGuard is put together, and why it is shaped this way.

---

## The one-paragraph version

PhishGuard is a **self-hosted** anti-phishing filter for a single Gmail
account. A background task polls the inbox over the Gmail API, runs each new
message through a scoring engine made of small independent analysers, writes
the result to a local SQLite database, and applies a Gmail label to anything
that scores high enough. A React dashboard reads that database through a
small HTTP API and shows both the aggregate picture and the reasoning behind
every individual verdict.

Nothing leaves the machine it runs on except calls to Google's own API.

---

## The shape of the system

```
                         ┌──────────────────────┐
                         │      Gmail API       │
                         │  (Google's servers)  │
                         └──────────┬───────────┘
                                    │ OAuth 2.0, gmail.modify scope
                                    │ read messages · add labels
                    ┌───────────────┴───────────────┐
                    │                               │
        ┌───────────▼───────────┐       ┌───────────▼───────────┐
        │   gmail/client.py     │       │   gmail/client.py     │
        │   list + fetch        │       │   ensure/apply label  │
        └───────────┬───────────┘       └───────────▲───────────┘
                    │ ParsedMessage                 │
                    ▼                               │
        ┌───────────────────────────────────────────┴───────────┐
        │                      scanner.py                       │
        │   for each new message: analyse → persist → label      │
        └───────────┬───────────────────────────────┬───────────┘
                    │                               │
        ┌───────────▼───────────┐       ┌───────────▼───────────┐
        │    analysis/ engine   │       │      SQLite (db.py)   │
        │  auth · spoofing ·    │       │   scanned_emails      │
        │  urls · typosquat ·   │       │   one row per message │
        │  language             │       └───────────┬───────────┘
        │  → score + findings   │                   │
        └───────────────────────┘                   │
                                                    │ SQLAlchemy
                    ┌───────────────────────────────▼───────────┐
                    │            FastAPI (main.py)              │
                    │  /api/health  /api/stats  /api/emails     │
                    │  /api/emails/{id}  POST /api/scan         │
                    │  + serves frontend/dist as static files   │
                    └───────────────────┬───────────────────────┘
                                        │ JSON over HTTP
                    ┌───────────────────▼───────────────────────┐
                    │        React dashboard (frontend/)        │
                    │  KPI tiles · charts · message table ·     │
                    │  per-message explainability panel         │
                    └───────────────────────────────────────────┘
```

The `poller` sits alongside the FastAPI app in the same process and calls
`scanner.scan_once()` on a timer.

---

## The five decisions that shaped everything else

### 1. Label, never delete

PhishGuard's only write action against a mailbox is **adding a Gmail label**
(`PhishGuard/Suspicious` or `PhishGuard/Junk`). Flagged mail stays in the
inbox, unread state untouched.

This is not timidity, it is what makes the tool usable. A heuristic filter is
wrong sometimes. If being wrong means a job offer lands in a folder you never
open, the correct response is to not run the filter at all. If being wrong
means a label you can remove in one click, you can leave it running for weeks
and actually tune it against real mail.

It also shrinks the blast radius of a bug. The worst outcome of a total
malfunction here is a mislabelled inbox — not lost mail.

The OAuth scope enforces this at the API level: `gmail.modify` grants reading
and label changes and **does not** grant permanent deletion. Even a
compromised or badly written version of this code could not destroy mail with
the token it holds.

### 2. Explainable scores, not a black box

Every analyser returns *findings* — `{code, label, weight, detail}` — not just
a number. The engine sums the weights into a 0–100 score and keeps the whole
list. That list is stored with the message and rendered in the dashboard.

This matters for two reasons:

- **Trust.** "This is phishing, confidence 0.87" is unfalsifiable. "DMARC
  failed (+30), the sender domain `paypa1-secure.example` impersonates paypal
  (+30), and the link text says paypal.com while pointing at
  paypa1-secure.example (+25)" is checkable in five seconds.
- **Tuning.** When PhishGuard is wrong, the findings list tells you exactly
  which weight or threshold to change. Without it, tuning is guesswork.

### 3. Rules, not machine learning

A classifier trained on a labelled corpus would very likely score better on a
benchmark. It was still the wrong choice here:

- There is no training data. One personal inbox is a few thousand messages,
  overwhelmingly legitimate, with maybe a dozen genuine phishing attempts.
- A model cannot explain itself in the way point 2 requires.
- Model weights are a supply-chain and privacy question. Rules in a Python
  file are readable, reviewable, and diffable.
- Signals like "DMARC failed" and "the link text does not match the href" are
  *deterministic facts about the message*, not statistical patterns. Learning
  them from data would be a slower path to a worse version of a rule anyone
  can read.

The tradeoff is honest: this catches commodity phishing — the mass-mailed
lures that make up almost all of what reaches a personal inbox. It will not
catch a targeted, well-authenticated, carefully written spear-phishing email.
Nothing that runs on a laptop will.

### 4. One process, one file, no infrastructure

The API, the poller, and the static file server are one uvicorn process. The
database is one SQLite file. There is no Redis, no Celery, no Postgres, no
Docker requirement.

At this scale the workload is a few dozen messages every couple of minutes,
handled by one background task. Every piece of infrastructure a project like
this adds is a service that has to be running for the app to work, and this
one has to survive being ignored for a week and still work when you come back.

The seams are still in the right places, though: `Scanner` takes a
`GmailClient` in its constructor, `db.py` builds the engine from a URL string,
and every aggregate is a SQLAlchemy query rather than raw SQL. Moving to
Postgres is a `DATABASE_URL` change; moving the poller to a worker process is
a call site change.

### 5. The dashboard is a client, not the app

The React app is a pure consumer of the HTTP API — it holds no logic the
backend does not also enforce. You can `curl` every number on the screen. The
scanner works with the dashboard turned off, and the dashboard is the thing
that makes the scanner's judgements legible.

In production FastAPI serves the built frontend itself, so the whole thing is
one origin on one port. In development Vite serves it with a proxy, so the
code path (`fetch('/api/...')`) is identical in both.

---

## Request and data flow

### A message being scanned

1. `Poller._run` wakes up (every `POLL_INTERVAL_SECONDS`, default 120).
2. It calls `Scanner.scan_once()` via `asyncio.to_thread` — the Google client
   library is blocking, and running it directly on the event loop would stall
   every HTTP request for the duration of the scan.
3. `scan_once` walks Gmail's message IDs matching
   `in:inbox newer_than:{INITIAL_LOOKBACK_DAYS}d`, **following pagination**
   via `iter_message_ids`.
4. For each ID **not already in the database** (checked by the unique
   `gmail_id` column), it fetches the full message and converts the Gmail JSON
   into a `ParsedMessage`. It stops after analysing `POLL_MAX_RESULTS` *new*
   messages and resumes from there next cycle.

   > **This split matters.** `POLL_MAX_RESULTS` bounds how many messages are
   > *analysed*, not how many ids are *fetched*. An earlier version capped the
   > id list instead, which meant asking Gmail for the newest N every cycle,
   > finding them all already scanned, and reporting "0 new" forever — so
   > anything older than the newest N was permanently unreachable. Listing ids
   > is cheap and paginated; fetching and analysing messages is the expensive
   > part, and that is what deserves a budget.
5. `analyze(msg)` runs every analyser and returns score, verdict, findings,
   and the three authentication results.
6. If the verdict is `junk` or `suspicious`, the label is applied. **Labelling
   failures are caught and logged** — the scan record is still written, so a
   Gmail hiccup never loses the analysis.
7. The row is committed. One commit per message, so a crash halfway through a
   batch leaves the completed work intact.

### A dashboard page load

1. The browser loads `index.html` and the JS/CSS bundles from FastAPI.
2. React mounts and issues three requests: `/api/health`, `/api/stats?days=14`,
   and `/api/emails?days=14&limit=100`.
3. `/api/stats` runs the aggregate queries in `stats.py` — all of them scoped
   to the same calendar-day window — and returns one JSON object holding every
   number the dashboard needs.
4. The page renders. Every 60 seconds it refetches in the background, holding
   the previous render at reduced opacity rather than flashing to skeletons.
5. Clicking a row opens the explainability panel from data already in hand —
   the list endpoint returns the full findings array, so there is no second
   request and no spinner.

---

## Where the boundaries are

| Boundary | Enforced by | Why it is there |
|---|---|---|
| Gmail format ↔ analysis | `ParsedMessage` | The engine never sees Gmail JSON. That is why the same engine can score a raw `.eml` file offline, with no OAuth at all. |
| Analysis ↔ storage | `AnalysisResult` | Analysers return values; only `scanner.py` writes rows. |
| Storage ↔ HTTP | Pydantic schemas | The API's shape is declared separately from the database's, so a column rename is not automatically an API break. |
| Backend ↔ frontend | The JSON API | The dashboard has no privileged access. Anything it can show, `curl` can show. |

The first of those is the one that pays off most often. Because
`analysis/eml.py` can build a `ParsedMessage` from a raw RFC 5322 message, the
entire detection engine is testable — and usable from the command line — with
no Google account, no network, and no credentials:

```bash
python -m app.tools.scan_eml samples/phish_paypal.eml
```

---

## What is deliberately not here

- **No message bodies in the database.** Subjects, headers, and findings are
  stored; body text is analysed in memory and dropped. A stolen
  `phishguard.db` reveals metadata, not correspondence.
- **No outbound network calls beyond Gmail.** No reputation APIs, no URL
  detonation services, no telemetry. Every check is local.
- **No multi-user support.** One database, one mailbox, one set of OAuth
  credentials. Adding accounts would mean a user table, per-user tokens, and
  authentication on the API — a different project.
- **No authentication on the API.** It binds to localhost and is meant to stay
  there. See the note in [SETUP.md](SETUP.md#a-word-on-exposure) before putting
  it on a network.

---

## Further reading

| Document | What it covers |
|---|---|
| [BACKEND.md](BACKEND.md) | FastAPI, SQLAlchemy, Pydantic, uvicorn — what each does, why it was chosen, and a file-by-file tour |
| [DETECTION.md](DETECTION.md) | SPF/DKIM/DMARC explained, every signal, every weight, and how to tune them |
| [FRONTEND.md](FRONTEND.md) | React, Vite, Recharts, and the visual-design rules the dashboard follows |
| [SETUP.md](SETUP.md) | Getting it running, including the Google Cloud OAuth steps |
