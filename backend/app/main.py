"""PhishGuard FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.guards import require_client_header
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


@app.post("/api/scan", dependencies=[Depends(require_client_header)])
async def trigger_scan() -> dict:
    """Manually run a scan cycle now (useful for testing / on-demand refresh)."""
    scanner = Scanner()
    summary = await asyncio.to_thread(scanner.scan_once)
    return summary


async def _shutdown_soon(delay: float = 0.25) -> None:
    """Stop the server, after giving the HTTP response time to reach the client.

    Shutting down inside the request handler would kill the connection before
    the browser ever saw the reply, so the UI could not tell "stopped" from
    "crashed".

    SIGINT is uvicorn's own graceful path: it runs the lifespan shutdown, which
    stops the poller and lets any in-flight scan finish. raise_signal delivers
    it to the main thread, which is where uvicorn's handler lives. The os._exit
    afterwards is a backstop for the case where something swallows the signal --
    without it a failed shutdown would leave a server that says it stopped and
    did not.
    """
    await asyncio.sleep(delay)
    log = logging.getLogger("phishguard")
    log.info("Shutdown requested via API")
    try:
        signal.raise_signal(signal.SIGINT)
    except Exception:  # pragma: no cover - platform-dependent
        log.exception("Graceful shutdown failed; exiting hard")
        os._exit(0)

    await asyncio.sleep(5)
    log.warning("Graceful shutdown did not complete in 5s; exiting hard")
    os._exit(0)


@app.post("/api/shutdown", dependencies=[Depends(require_client_header)])
async def shutdown() -> dict:
    """Stop the PhishGuard server.

    Exists so the dashboard and the extension can offer a Stop button. Nothing
    in a browser can *start* a local process -- that is what the logon task is
    for -- but stopping one it can already talk to is just a request.
    """
    asyncio.create_task(_shutdown_soon())
    return {"status": "stopping"}


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
