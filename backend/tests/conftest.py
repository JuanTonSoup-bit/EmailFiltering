"""Pytest bootstrap.

This module runs before any test module is imported, which is the only
moment at which the database location can still be changed: app.config
builds its Settings object at import time, and app.db opens the engine at
import time from that object. Setting DATABASE_URL here means a test run can
never read or write the real data/phishguard.db.

Environment variables take precedence over a .env file in pydantic-settings,
so this holds even once a developer has created backend/.env.
"""

from __future__ import annotations

import os
import pathlib
import tempfile

_TEST_DB = pathlib.Path(tempfile.gettempdir()) / "phishguard_pytest.db"

# A file rather than sqlite:///:memory: on purpose: an in-memory SQLite
# database is scoped to a single connection, and the app's engine, its
# session factory, and the TestClient's worker thread do not reliably share
# one. A temp file behaves like the real thing for every code path.
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

# Point OAuth at paths that certainly do not exist, so nothing in a test run
# can stumble into a real Google sign-in or a cached token.
os.environ.setdefault("GMAIL_CREDENTIALS_FILE", str(_TEST_DB.parent / "no-such-credentials.json"))
os.environ.setdefault("GMAIL_TOKEN_FILE", str(_TEST_DB.parent / "no-such-token.json"))

if _TEST_DB.exists():
    _TEST_DB.unlink()
