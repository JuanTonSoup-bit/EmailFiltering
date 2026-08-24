"""Background poller: periodically runs a scan cycle."""

from __future__ import annotations

import asyncio
import logging

from .config import settings
from .scanner import Scanner

log = logging.getLogger("phishguard.poller")


class Poller:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        # Deliberately not created here. An asyncio.Event binds itself to
        # whichever event loop first awaits it, and the module-level Poller
        # in main.py is constructed at import time, before any loop exists.
        # Building it in start() -- which always runs inside the loop -- also
        # means a restarted app gets a fresh Event instead of awaiting one
        # owned by a loop that has already closed.
        self._stop: asyncio.Event | None = None
        self._scanner: Scanner | None = None
        self.last_summary: dict | None = None

    async def _run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                if self._scanner is None:
                    self._scanner = Scanner()
                # Gmail client is blocking; run off the event loop.
                self.last_summary = await asyncio.to_thread(
                    self._scanner.scan_once
                )
            except Exception:
                log.exception("Scan cycle failed")
            # Sleep until the interval elapses OR shutdown is requested,
            # whichever comes first. A plain asyncio.sleep would make the app
            # hang for up to poll_interval_seconds on Ctrl+C.
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.poll_interval_seconds
                )
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._stop = asyncio.Event()
            self._task = asyncio.create_task(self._run(self._stop))
            log.info("Poller started (interval=%ss)", settings.poll_interval_seconds)

    async def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()
        task, self._task, self._stop = self._task, None, None
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                # Shutdown raced with cancellation; the loop is going away
                # anyway, so there is nothing left to clean up.
                pass
            log.info("Poller stopped")
