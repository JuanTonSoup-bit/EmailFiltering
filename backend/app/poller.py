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
        self._stop = asyncio.Event()
        self._scanner: Scanner | None = None
        self.last_summary: dict | None = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._scanner is None:
                    self._scanner = Scanner()
                # Gmail client is blocking; run off the event loop.
                self.last_summary = await asyncio.to_thread(
                    self._scanner.scan_once
                )
            except Exception:
                log.exception("Scan cycle failed")
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=settings.poll_interval_seconds
                )
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._run())
            log.info("Poller started (interval=%ss)", settings.poll_interval_seconds)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None
