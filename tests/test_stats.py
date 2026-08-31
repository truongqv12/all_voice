"""Live usage stats — presence tracker + public GET /v1/stats (all `not synth`).

Unit coverage of the in-memory presence window/eviction, plus HTTP checks that
the endpoint is public, self-excluded (the poll must not inflate "active"), and
never leaks an IP.
"""

from __future__ import annotations

import os

os.environ.setdefault("API_KEYS", "test-key")

from app.presence import Presence  # noqa: E402


# --- presence tracker -------------------------------------------------------

def test_active_count_within_window(monkeypatch):
    p = Presence()
    clock = [1000.0]
    monkeypatch.setattr("app.presence.time.monotonic", lambda: clock[0])

    p.touch("a")
    p.touch("b")
    assert p.active_count(window_s=180) == 2


def test_active_count_evicts_outside_window(monkeypatch):
    p = Presence()
    clock = [1000.0]
    monkeypatch.setattr("app.presence.time.monotonic", lambda: clock[0])

    p.touch("a")           # seen at t=1000
    clock[0] = 1100.0
    p.touch("b")           # seen at t=1100
    clock[0] = 1200.0      # window 180s -> cutoff 1020: "a" is stale, "b" fresh
    assert p.active_count(window_s=180) == 1
    # "a" was evicted from the map, not merely skipped.
    assert "a" not in p._seen


def test_touch_dedups_same_ip(monkeypatch):
    p = Presence()
    clock = [1000.0]
    monkeypatch.setattr("app.presence.time.monotonic", lambda: clock[0])

    p.touch("a")
    clock[0] = 1050.0
    p.touch("a")           # same IP refreshes, does not double-count
    assert p.active_count(window_s=180) == 1


# --- HTTP endpoint ----------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.presence import presence  # noqa: E402

_client = TestClient(app)


def test_stats_public_shape_and_self_excluded():
    presence.reset()
    r = _client.get("/v1/stats")
    assert r.status_code == 200  # no key needed
    body = r.json()
    assert set(body) == {"active", "total"}  # aggregate only, no IP field
    assert body["active"] == 0  # polling /v1/stats must not count itself


def test_stats_counts_a_real_request():
    presence.reset()
    _client.get("/v1/models")  # a normal /v1 hit marks the caller active
    assert _client.get("/v1/stats").json()["active"] == 1
