"""PhishGuard FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router as api_router
from .db import init_db
from .poller import Poller
from .scanner import Scanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

poller = Poller()

# Serve the built React app if present (frontend/dist copied or path-relative).
_FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "frontend",
    "dist",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Poller starts lazily; if Gmail creds are missing it logs and retries,
    # so the dashboard/API stay up even before OAuth is completed.
    poller.start()
    try:
        yield
    finally:
        await poller.stop()


app = FastAPI(title="PhishGuard", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.post("/api/scan")
async def trigger_scan() -> dict:
    """Manually run a scan cycle now (useful for testing / on-demand refresh)."""
    import asyncio

    scanner = Scanner()
    summary = await asyncio.to_thread(scanner.scan_once)
    return summary


# Mount the frontend build last so /api takes precedence.
if os.path.isdir(_FRONTEND_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
