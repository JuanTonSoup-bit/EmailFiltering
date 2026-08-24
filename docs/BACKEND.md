# Backend

What every library in the backend actually does, why it is in this project,
and a file-by-file tour of the code.

---

## Part 1 — The stack, explained

### FastAPI

**What it is.** A Python web framework for building HTTP APIs. You write a
plain function, decorate it with the route it should answer, and FastAPI turns
it into an HTTP endpoint.

```python
@router.get("/stats", response_model=DashboardStats)
def stats(days: int = Query(14, ge=1, le=90),
          session: Session = Depends(get_session)) -> DashboardStats:
    return build_dashboard(session, days=days)
```

That single function does considerably more than it looks like:

- **Routing.** `GET /api/stats` reaches this function.
- **Parsing and validation.** `days` is read from the query string, converted
  to `int`, and checked against `ge=1, le=90`. A request for `?days=500` gets
  a `422` with a precise error message — and the function body never runs.
  Invalid input is rejected at the door rather than defended against inside
  every function.
- **Dependency injection.** `Depends(get_session)` means FastAPI calls
  `get_session()`, hands the yielded database session in, and runs the
  generator's cleanup afterwards. The endpoint cannot leak a connection by
  forgetting to close one, because it never opens one.
- **Serialisation.** `response_model=DashboardStats` converts the returned
  object to JSON according to that schema — and strips anything not declared
  in it, so a field added to the database does not silently start appearing in
  API responses.
- **Documentation.** All of the above is emitted as an OpenAPI spec, which is
  why `http://localhost:8000/docs` is a working, clickable API browser that
  nobody had to write.

**Why FastAPI here.** Three reasons, in order of weight:

1. *Validation is declarative and free.* The type hints are not decoration —
   they are the validation rules. `verdict: str | None = Query(None,
   pattern="^(clean|junk|suspicious)$")` is the entire defence against a
   malformed verdict filter, and it lives in the signature where you can see
   it.
2. *It is async-native.* The poller is a long-lived `asyncio` task living in
   the same process as the API. FastAPI's `lifespan` gives that task a
   first-class place to start and stop. Doing this in a WSGI framework means
   a second process and something to supervise it.
3. *The interactive docs are the API contract.* For a portfolio project, a URL
   that lets a reviewer poke the API without reading a line of code is worth a
   lot.

**What was considered instead.** Flask is smaller and more familiar, but
validation, serialisation, and OpenAPI would all be hand-rolled or bolted on
— and the background poller would need a separate process. Django is a
much larger framework whose main strengths (ORM conventions, admin, auth,
templating) are things this project does not use.

### Uvicorn

**What it is.** The ASGI server that actually accepts TCP connections and
speaks HTTP. FastAPI defines *what* the responses are; uvicorn is what puts
them on a socket.

**Why it is here.** FastAPI is ASGI-only, and uvicorn is its reference server.
`uvicorn[standard]` pulls in `uvloop`/`httptools` where available for speed;
neither matters at this scale, but they cost nothing.

**Why it is not gunicorn + workers.** Multiple worker processes would mean
multiple *pollers*, each independently scanning the same inbox and racing to
insert the same `gmail_id`. Single process is not a limitation here, it is a
correctness requirement given the current design.

### SQLAlchemy

**What it is.** Python's ORM (object-relational mapper) and SQL toolkit. It
does two distinct jobs:

1. **Mapping.** A Python class describes a table. Instances of it are rows.

   ```python
   class ScannedEmail(Base):
       __tablename__ = "scanned_emails"
       id: Mapped[int] = mapped_column(Integer, primary_key=True)
       gmail_id: Mapped[str] = mapped_column(String(64), index=True)
       verdict: Mapped[str] = mapped_column(String(16), default="clean", index=True)
       findings: Mapped[list] = mapped_column(JSON, default=list)
   ```

   `Base.metadata.create_all()` turns those declarations into `CREATE TABLE`
   statements — the schema is defined once, in Python.

2. **Query building.** SQL is composed as Python expressions:

   ```python
   session.execute(
       select(ScannedEmail.verdict, func.count())
       .where(ScannedEmail.scanned_at >= since)
       .group_by(ScannedEmail.verdict)
   )
   ```

   which becomes `SELECT verdict, count(*) FROM scanned_emails WHERE
   scanned_at >= ? GROUP BY verdict`.

**Why an ORM at all**, when the schema is one table:

- **Parameterisation is automatic.** Every value goes in as a bound parameter.
  SQL injection is not a bug you can write here without going out of your way,
  and for a security tool that is not a small thing.
- **The type mapping is done for you.** `findings` is a Python list of dicts
  in the code and JSON in the column. `scanned_at` is a timezone-aware
  `datetime` in Python and a stored timestamp in SQLite. No serialisation code
  is written anywhere in this project.
- **Migrating databases is a URL change.** `create_engine(settings.database_url)`
  is the only place the database technology is named. SQLite for a laptop,
  Postgres for a server, no query rewrites.
- **The aggregate queries would be genuinely unpleasant as strings.**
  `stats.py` builds five different grouped aggregations that all share one
  window predicate. As f-strings that is a maintenance hazard; as composed
  expressions it is ordinary code.

**The modern 2.0 style is used throughout**: `Mapped[...]` /
`mapped_column(...)` for models, `select()` with `session.scalars()` /
`session.execute()` for queries. The older `Query` API still works but is
legacy, and `Mapped[]` annotations mean type checkers understand the models.

**Session configuration**, from `db.py`:

```python
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

- `autoflush=False` — do not implicitly write pending changes before every
  query. Writes happen where `session.add()` and `session.commit()` are
  called, and nowhere else.
- `expire_on_commit=False` — after a commit, objects stay usable. With the
  default, touching any attribute of a just-committed object fires a fresh
  `SELECT`, which for an API that returns the object it just wrote is pure
  waste.

### SQLite

**What it is.** A complete SQL database that is one file and no server
process. The library is part of the Python standard library.

**Why it fits.** The workload is a few hundred rows a day, written by one
process, read by one dashboard. There is no concurrency to speak of. Against
that, a Postgres dependency would mean a service the user must install,
configure, back up, and keep running — for a tool whose entire value is that
you can set it going and forget about it.

**The one bit of care it needs:**

```python
_connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
```

SQLite's Python driver defaults to refusing use of a connection from a thread
other than the one that opened it. FastAPI runs sync endpoints in a thread
pool, and the poller runs its scans in `asyncio.to_thread`, so connections
legitimately move between threads. Disabling the check is correct here because
SQLAlchemy's connection pool already guarantees one connection is not used by
two threads simultaneously.

**Where it would stop being the right answer:** multiple concurrent writers.
SQLite locks the whole database for a write. One poller and a read-only
dashboard never contend; four poller processes would.

### Pydantic and pydantic-settings

**What it is.** A validation and serialisation library built on Python type
hints. A class declares fields with types; Pydantic enforces them at runtime.

**Two distinct jobs in this project.**

*Job one — API schemas* (`schemas.py`). These define the JSON shape of every
response:

```python
class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    verdict: str
    findings: list[Finding]
    scanned_at: dt.datetime
```

`from_attributes=True` lets Pydantic read a SQLAlchemy object directly instead
of requiring a dict. This is why the endpoints can `return
list(session.scalars(stmt))` and get correct JSON — FastAPI runs the ORM
objects through this schema.

Keeping schemas separate from models is deliberate. The database table has
`thread_id`; the API does not expose it. If they were the same class, every
column added for internal use would immediately become part of the public
contract.

*Job two — configuration* (`config.py`). `BaseSettings` reads values from
environment variables and a `.env` file, with types and defaults:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    poll_interval_seconds: int = 120
    suspicious_threshold: int = 50
```

`SUSPICIOUS_THRESHOLD=60` in `.env` becomes `settings.suspicious_threshold ==
60`, as an `int`, validated at startup. A typo like `SUSPICIOUS_THRESHOLD=abc`
fails immediately with a clear message rather than producing a `TypeError`
during the first scan an hour later. Environment variables take precedence
over `.env`, which is what lets the test suite redirect the database without
touching any file.

> **Version note.** `requirements.txt` pins `pydantic>=2.11.7`. Pydantic's core
> is written in Rust; older releases have no prebuilt wheel for Python 3.14 and
> pip tries to compile from source, which fails without a Rust toolchain. 2.11.7
> is the first release shipping cp314 wheels. This is a real trap on this
> machine, where 3.14 is the default Python.

### google-api-python-client and google-auth-oauthlib

**What they are.** Google's official client libraries. `google-auth-oauthlib`
runs the OAuth 2.0 flow that gets a token; `google-api-python-client` uses that
token to call the Gmail REST API.

**How the OAuth flow works here** (`gmail/auth.py`):

1. On first run, there is no `token.json`, so `InstalledAppFlow` reads the
   client secret from `credentials.json`, opens a browser, and asks *you* to
   consent.
2. The resulting access token **and refresh token** are written to
   `token.json`.
3. On later runs the token is loaded from that file. If it has expired, the
   refresh token silently gets a new one.

So the browser prompt happens exactly once. Both `credentials.json` and
`token.json` are in `.gitignore` — `token.json` in particular is a live
credential to a mailbox.

**The scope is the security control:**

```python
gmail_scopes = ("https://www.googleapis.com/auth/gmail.modify",)
```

`gmail.modify` permits reading messages and changing labels. It does **not**
permit permanent deletion, and it does not permit sending. The narrower
`gmail.readonly` would not allow labelling; the broader `https://mail.google.com/`
would allow destroying mail. `modify` is the smallest scope that does the job,
which is the only correct way to choose one.

**Why not IMAP?** IMAP would avoid OAuth setup, but it requires storing a
password or app password in plaintext, has no equivalent of a scoped
capability, and Google's IMAP support for new applications is on the way out.
OAuth is more setup once and better security forever.

### tldextract

**What it is.** A library that splits a hostname into subdomain, domain, and
suffix using the Public Suffix List.

**Why it is not optional.** Getting the *registrable* domain right is the
foundation of half the detection logic, and naive string splitting gets it
wrong constantly:

| Host | Naive "last two labels" | Correct registrable domain |
|---|---|---|
| `mail.google.com` | `google.com` ✅ | `google.com` |
| `foo.co.uk` | `co.uk` ❌ | `foo.co.uk` |
| `a.b.github.io` | `github.io` ❌ | `b.github.io` |

Comparing a From domain against a Reply-To domain, deciding whether a link
leaves the sender's domain, and typosquat matching all depend on this being
right. `co.uk` being treated as a domain would break every comparison
involving a UK sender.

### pytest

**What it is.** Python's de-facto test framework. Plain functions named
`test_*`, plain `assert` statements, and fixtures for shared setup.

**How it is used here:**

- `tests/conftest.py` runs before any test module is imported and redirects
  `DATABASE_URL` to a throwaway file. It has to be there rather than in a
  fixture because `app.config` builds its settings at import time and `app.db`
  opens the engine at import time — by the time a fixture runs, it is too
  late.
- `tests/test_engine.py`, `test_typosquat.py`, `test_eml.py` — pure unit tests
  of the detection logic. No database, no network.
- `tests/test_stats.py` — the aggregate queries, against an in-memory SQLite
  database created per test.
- `tests/test_api.py` — the real FastAPI app driven through Starlette's
  `TestClient`: real routing, real dependency injection, real serialisation,
  no network socket.

---

## Part 2 — File-by-file tour

### `app/config.py`

Every tunable in one place, loaded from the environment. Thresholds, poll
interval, label names, file paths, OAuth scope. Nothing else in the codebase
reads `os.environ`.

### `app/db.py`

Engine, session factory, and `Base`.

- `_ensure_sqlite_dir()` creates the parent directory for a SQLite file URL
  before the engine opens it — otherwise a fresh clone fails on first run with
  "unable to open database file", which is a confusing message for a missing
  folder.
- `init_db()` imports `models` before calling `create_all()`. The import is
  what registers the table on `Base.metadata`; without it, `create_all()`
  cheerfully creates nothing.
- `get_session()` is the FastAPI dependency: yield a session, close it in
  `finally`, always.

### `app/models.py`

The single table, `scanned_emails`. Notable columns:

- `gmail_id` with a **unique constraint**. This is the idempotency key — it is
  what makes re-scanning safe. Rescanning an already-seen message is skipped
  by a lookup on this column, and even a race that got past the lookup would
  be stopped by the constraint.
- `findings` as a `JSON` column. The findings list is variable-length,
  schemaless, and only ever read as a whole for display. A second table plus a
  join would buy queryability nobody needs.
- Indexes on `verdict`, `from_domain`, and `scanned_at` — the three columns
  every dashboard query filters or groups by.
- `scanned_at` is `DateTime(timezone=True)` defaulting to
  `datetime.now(timezone.utc)`. Storing UTC and converting at display time is
  the only approach that survives a laptop crossing a timezone or a DST
  boundary.

### `app/analysis/`

Covered in depth in [DETECTION.md](DETECTION.md). Structurally: `message.py`
defines the format-neutral `ParsedMessage`; `auth.py`, `spoofing.py`,
`urls.py`, `typosquat.py`, and `language.py` are independent analysers that
each answer one question; `engine.py` runs them and turns their answers into a
score and a verdict; `eml.py` builds a `ParsedMessage` from a raw `.eml` file
so all of it works with no Gmail account.

### `app/gmail/client.py`

Wraps the Gmail API.

- `_extract_bodies` walks the MIME tree recursively, base64url-decoding
  `text/plain` and `text/html` parts. Gmail nests parts arbitrarily
  (`multipart/mixed` → `multipart/alternative` → the actual text), so a
  non-recursive version finds nothing on a large share of real mail.
- `_parse` uses `email.utils.parseaddr` rather than a regex to split
  `"Display Name" <addr@example.com>` — that format has more edge cases than
  it appears to.
- Labels are cached in `_label_cache`. Without it, every flagged message would
  cost an extra `labels.list` round trip.
- `ensure_label` creates the label if it does not exist, so first run needs no
  manual setup in Gmail.

### `app/scanner.py`

One scan cycle: walk ids, skip already-seen, fetch, analyse, label, persist.

**The id stream is paginated and the analysis budget is separate.**
`client.iter_message_ids()` follows Gmail's `nextPageToken` across pages;
`scan_once` consumes that stream until it has analysed `POLL_MAX_RESULTS`
messages it has not seen before, then stops and resumes there next cycle.

Getting this wrong is subtle and was a real bug: capping the *id list* rather
than the *analysis count* meant requesting the newest N every cycle, finding
all N already in the database, and reporting "0 new" indefinitely. A mailbox
with 800 messages in the window would sit permanently at 25 scanned, with no
error and nothing in the logs to suggest anything was wrong.

The critical detail is the `try/except` around labelling:

```python
try:
    self.client.apply_label(gmail_id, label_applied)
    flagged += 1
except Exception:
    log.exception("Failed to apply label to %s", gmail_id)
    label_applied = None
```

A transient Gmail error must not cost the analysis. The row is written with
`label_applied = None`, which is both true and visible in the dashboard.

Committing per message rather than per batch means an interruption keeps
everything already processed.

### `app/poller.py`

The background loop. Two things in it are worth knowing about:

**`asyncio.to_thread` for the scan.** The Google client is synchronous and
blocking. Calling it directly on the event loop would freeze every HTTP
request for the length of a scan. `to_thread` moves it to a worker thread and
lets the loop keep serving.

**The stop `Event` is created in `start()`, not `__init__`.** An
`asyncio.Event` binds to the event loop that first awaits it, and the
module-level `Poller()` in `main.py` is constructed at import time, before any
loop exists. Creating it in `start()` — which always runs inside the loop —
also means a restarted app gets a fresh Event rather than awaiting one owned
by a closed loop. (This was a real bug, caught by the API tests: the second
`TestClient` in a run failed with *"is bound to a different event loop"*.)

The sleep is `wait_for(stop.wait(), timeout=interval)` rather than
`asyncio.sleep(interval)`, so shutdown is immediate instead of taking up to
two minutes.

### `app/stats.py`

Every dashboard aggregate, all scoped to the same window.

`window_start(days)` anchors to **midnight UTC**, not "now minus N days":

```python
today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
return today - timedelta(days=days - 1)
```

The timeline groups by `strftime('%Y-%m-%d', scanned_at)`. A rolling cutoff
would slice the oldest day in half, producing a partial column that looks like
a quiet day rather than a truncated one. Anchoring to midnight also lets the
front end construct exactly the same date range locally and have the two
agree.

The window applies to *every* aggregate, not just the timeline. A date filter
that left some cards on all-time totals would put numbers on screen that
cannot be reconciled — "3 flagged this week" beside a sender list totalling 40.

### `app/api/routes.py` and `app/main.py`

The five endpoints, plus lifespan and static file serving.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness. The dashboard's connection pill polls it. |
| `GET /api/stats?days=` | Every dashboard aggregate in one object. |
| `GET /api/emails?verdict=&days=&limit=&offset=` | Scanned messages, newest first. |
| `GET /api/emails/{id}` | One message with its findings. |
| `POST /api/scan` | Run a scan cycle now instead of waiting for the poller. |
| `POST /api/shutdown` | Stop the server. Backs the Stop button in the dashboard and extension. |

Both POST endpoints sit behind `require_client_header` (see
`app/api/guards.py` below). GET endpoints are deliberately unguarded so curl
and the address bar stay usable.

`lifespan` is the modern replacement for `@app.on_event("startup")`: code
before `yield` runs at startup, code after runs at shutdown, and the `finally`
guarantees the poller is stopped even on an unclean exit.

The static mount is last, so `/api/*` always wins over the frontend's routes,
and it is conditional on `frontend/dist` existing — the API works fine before
the frontend has ever been built.

### `app/api/guards.py`

One dependency, `require_client_header`, applied to both POST endpoints.

The API has no authentication, which is fine for reads. Writes are different:
a browser will send a cross-origin POST to `127.0.0.1` from **any page you
happen to be visiting**, and with `mode: 'no-cors'` the response is unreadable
to the attacker but *the request still arrives*. Without a guard, any website
could trigger scans or silently switch the filter off.

Requiring a custom header is the fix, because a custom header is exactly what
forces the browser to send a CORS preflight first — and the preflight is
checked against this app's origin allowlist. A page on someone else's site
gets its preflight refused and the real request is never sent. Pages cannot
opt out; it is enforced by the browser.

It is not authentication and does not pretend to be. Anything already running
locally can set a header. It closes the specific hole where a *remote web
page* drives your local API.

### `app/tools/`

- `scan_eml.py` — score a `.eml` file, or check a single domain for
  typosquatting, from the command line. No OAuth required.
- `seed_demo.py` — fill the database with realistic demo data so the dashboard
  can be run and reviewed without a Google account. Every row is produced by
  running synthetic messages through the **real** `analyze()` function, so the
  demo cannot drift away from what the engine actually does.

---

## Testing

```bash
cd backend
.venv/Scripts/python -m pytest -q     # Windows
.venv/bin/python -m pytest -q         # macOS / Linux
```

56 tests, roughly one second. They cover the scoring engine and each analyser,
typosquat technique classification, `.eml` parsing, every dashboard aggregate
including the window semantics, and every API endpoint including its failure
modes (out-of-range `days` → 422, unknown verdict → 422, missing id → 404,
scan without credentials → error that does not take the app down).

No test touches the network or the real database.
