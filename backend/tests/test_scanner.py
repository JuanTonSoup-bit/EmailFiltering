"""Tests for scan orchestration and Gmail id pagination.

The bug these exist to prevent: the original client fetched a single page of
message ids. Once the newest N were scanned, every later cycle got the same N
back, skipped them all as already-seen, and reported "0 new" -- so anything
older than the newest N was permanently unreachable and a backlog could never
drain.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.gmail.client import GmailClient
from app.scanner import Scanner


class FakeMessages:
    """Stands in for service.users().messages(), with real pagination."""

    def __init__(self, ids: list[str], page_size: int = 500):
        self.ids = ids
        self.page_size = page_size
        self.list_calls = 0

    def list(self, userId=None, q=None, maxResults=None, pageToken=None):
        self.list_calls += 1
        start = int(pageToken) if pageToken else 0
        size = min(self.page_size, maxResults or self.page_size)
        chunk = self.ids[start : start + size]
        nxt = start + size
        body = {"messages": [{"id": i} for i in chunk]}
        if nxt < len(self.ids):
            body["nextPageToken"] = str(nxt)

        class _Req:
            def execute(_self):
                return body

        return _Req()


def make_client(ids: list[str], page_size: int = 500) -> GmailClient:
    client = GmailClient.__new__(GmailClient)  # bypass __init__ / OAuth
    fake = FakeMessages(ids, page_size)

    class _Users:
        def messages(self):
            return fake

    class _Service:
        def users(self):
            return _Users()

    client.service = _Service()
    client._label_cache = {}
    client._fake = fake
    return client


def test_iter_message_ids_follows_pagination():
    client = make_client([f"m{i}" for i in range(1200)], page_size=500)
    got = list(client.iter_message_ids("in:inbox"))

    assert len(got) == 1200
    assert got[0] == "m0" and got[-1] == "m1199"
    assert client._fake.list_calls == 3  # 500 + 500 + 200


def test_iter_message_ids_respects_hard_limit():
    client = make_client([f"m{i}" for i in range(1200)], page_size=500)
    got = list(client.iter_message_ids("in:inbox", hard_limit=600))
    assert len(got) == 600


def test_list_message_ids_can_exceed_one_page():
    """The regression itself: asking for 700 must return 700, not 500."""
    client = make_client([f"m{i}" for i in range(1000)], page_size=500)
    assert len(client.list_message_ids("in:inbox", 700)) == 700


class RecordingScanner(Scanner):
    """Scanner with the Gmail fetch/label/analyse steps stubbed out."""

    def __init__(self, client, already: set[str]):
        self.client = client
        self.fetched: list[str] = []
        self._already = already


def test_backlog_drains_across_cycles(monkeypatch):
    """Each cycle must analyse a fresh batch, not re-offer the same newest N."""
    all_ids = [f"m{i}" for i in range(250)]
    scanned: set[str] = set()

    monkeypatch.setattr(settings, "poll_max_results", 100)

    def run_cycle() -> int:
        client = make_client(all_ids)
        picked: list[str] = []
        for gmail_id in client.iter_message_ids("in:inbox"):
            if gmail_id in scanned:
                continue
            if len(picked) >= settings.poll_max_results:
                break
            picked.append(gmail_id)
        scanned.update(picked)
        return len(picked)

    assert run_cycle() == 100
    assert run_cycle() == 100
    assert run_cycle() == 50   # the remainder
    assert run_cycle() == 0    # steady state
    assert len(scanned) == 250
