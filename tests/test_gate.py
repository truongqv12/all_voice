"""Phase 1 — anonymous tier + abuse gate (all `not synth`).

Unit-level coverage of the pieces the gate is built from (identity, rate bucket,
daily budget, admission control) plus HTTP-level checks of the tier kill-switch and
the clone-CRUD guard. Nothing here performs real synthesis.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

os.environ.setdefault("API_KEYS", "test-key")

from app.client_identity import Identity, Tier, client_ip, resolve_tier  # noqa: E402
from app.config import Settings  # noqa: E402
from app.limits import Overloaded, admit, reset_state  # noqa: E402
from app.quota import Quota, QuotaExceeded, RateLimited  # noqa: E402


def _request(peer: str, headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http", "method": "POST", "path": "/", "query_string": b"",
        "headers": raw, "client": (peer, 12345), "scheme": "http", "server": ("t", 80),
    }
    return Request(scope)


# --- client_ip: loopback-gated CF-Connecting-IP (#1) + normalisation (#9) ---

def test_client_ip_trusts_header_only_from_loopback():
    s = Settings()
    # Peer is loopback (nginx) -> the edge-provided IP is trusted.
    req = _request("127.0.0.1", {"CF-Connecting-IP": "203.0.113.7"})
    assert client_ip(req, s) == "203.0.113.7"


def test_client_ip_ignores_spoofed_header_from_non_loopback():
    s = Settings()
    # Peer is NOT loopback (a would-be spoofer) -> header ignored, socket IP used.
    req = _request("203.0.113.9", {"CF-Connecting-IP": "10.0.0.1"})
    assert client_ip(req, s) == "203.0.113.9"


def test_client_ip_collapses_ipv6_to_prefix():
    s = Settings()  # ip_key_ipv6_prefix defaults to 64
    req = _request("127.0.0.1", {"CF-Connecting-IP": "2001:db8:abcd:1234:5:6:7:8"})
    assert client_ip(req, s) == "2001:db8:abcd:1234::"


# --- resolve_tier: TRUSTED / ANON / 401 kill-switch ---

def test_resolve_tier_valid_key_is_trusted():
    s = Settings(api_keys="k1,k2", anon_enabled=True)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="k2")
    ident = resolve_tier(_request("127.0.0.1"), creds, s)
    assert ident.tier is Tier.TRUSTED


def test_resolve_tier_no_key_is_anon_when_enabled():
    s = Settings(anon_enabled=True)
    ident = resolve_tier(_request("127.0.0.1"), None, s)
    assert ident.tier is Tier.ANON


def test_resolve_tier_no_key_401_when_anon_disabled():
    s = Settings(anon_enabled=False)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        resolve_tier(_request("127.0.0.1"), None, s)
    assert exc.value.status_code == 401


# --- rate limit (token bucket) ---

def test_rate_bucket_allows_burst_then_429():
    q = Quota()
    s = Settings(anon_rate_per_min=0, anon_burst=3)  # no refill, capacity 3
    for _ in range(3):
        q.allow_rate("1.2.3.4", s)  # 3 allowed
    with pytest.raises(RateLimited):
        q.allow_rate("1.2.3.4", s)  # 4th empties -> 429


# --- daily budget (SQLite) + refund net-zero (#4) ---

def test_budget_chars_reserve_and_exceed(tmp_path):
    q = Quota(db_path=str(tmp_path / "q.db"))
    s = Settings(anon_chars_per_day=100)
    q.reserve_chars("ip", 60, s)
    q.reserve_chars("ip", 40, s)  # exactly at cap
    assert q.usage("ip")[0] == 100
    with pytest.raises(QuotaExceeded):
        q.reserve_chars("ip", 1, s)


def test_budget_refund_is_net_zero(tmp_path):
    q = Quota(db_path=str(tmp_path / "q.db"))
    s = Settings(anon_chars_per_day=1000)
    q.reserve_chars("ip", 500, s)
    q.refund_chars("ip", 500)
    assert q.usage("ip")[0] == 0


def test_budget_audio_seconds(tmp_path):
    q = Quota(db_path=str(tmp_path / "q.db"))
    s = Settings(anon_audio_seconds_per_day=10)  # 10_000 ms cap
    q.reserve_audio("ip", 9000, s)
    with pytest.raises(QuotaExceeded):
        q.reserve_audio("ip", 2000, s)  # 11s > 10s
    q.refund_audio("ip", 9000)
    assert q.usage("ip")[1] == 0


def test_budget_fails_closed_on_infra_error(tmp_path, monkeypatch):
    q = Quota(db_path=str(tmp_path / "q.db"))
    s = Settings(anon_chars_per_day=1000)
    import sqlite3
    def _boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(q, "_connect", _boom)
    with pytest.raises(QuotaExceeded):  # fail-CLOSED: never allow through (#15)
        q.reserve_chars("ip", 1, s)


# --- admission control: Overloaded + counter release (#12) ---

def test_admit_rejects_over_per_ip_concurrency():
    reset_state()
    s = Settings(anon_max_concurrent_per_ip=1, max_queue_waiters=50)

    async def scenario():
        async with admit("ip", s):  # holds the one slot
            with pytest.raises(Overloaded):
                async with admit("ip", s):  # 2nd from same IP -> rejected
                    pass

    asyncio.run(scenario())
    # After everything unwinds, the per-IP counter is back to baseline (#12).
    from app.limits import _state
    assert _state.ip_conc.get("ip", 0) == 0


def test_admit_releases_counter_on_body_exception():
    reset_state()
    s = Settings(anon_max_concurrent_per_ip=2, max_queue_waiters=50)

    async def scenario():
        with pytest.raises(ValueError):
            async with admit("ip", s):
                raise ValueError("boom inside body")

    asyncio.run(scenario())
    from app.limits import _state
    assert _state.ip_conc.get("ip", 0) == 0
    assert _state.waiters == 0


def test_admit_rejects_when_queue_full():
    reset_state()
    s = Settings(anon_max_concurrent_per_ip=99, max_queue_waiters=0)  # no waiter room

    async def scenario():
        with pytest.raises(Overloaded):
            async with admit("ip", s):
                pass

    asyncio.run(scenario())


# --- HTTP-level: kill-switch, rate limit, input cap (all reject before synth) ---

from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

_client = TestClient(app)
_SPEECH = {"model": "vieneu", "input": "Xin chào.", "voice": "Trúc Ly"}


def _override(settings: Settings):
    app.dependency_overrides[get_settings] = lambda: settings


def _clear_override():
    app.dependency_overrides.pop(get_settings, None)


def test_http_anon_disabled_returns_401():
    _override(Settings(anon_enabled=False, api_keys="test-key"))
    try:
        r = _client.post("/v1/audio/speech", json=_SPEECH)  # no key -> 401 in resolve_tier
        assert r.status_code == 401
    finally:
        _clear_override()


def test_http_rate_limit_returns_429():
    _override(Settings(anon_burst=0, anon_rate_per_min=0, api_keys="test-key"))
    try:
        r = _client.post("/v1/audio/speech", json=_SPEECH)  # empty bucket -> 429 before synth
        assert r.status_code == 429
        assert r.json()["error"]["type"] == "rate_limit_error"
    finally:
        _clear_override()


def test_http_anon_input_too_long_returns_400():
    _override(Settings(anon_max_chars_buffered=5, api_keys="test-key"))
    try:
        r = _client.post("/v1/audio/speech", json={**_SPEECH, "input": "x" * 50})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "input_too_long"
    finally:
        _clear_override()


def test_http_cache_hit_charges_budget_once_no_synth(monkeypatch):
    # A cache HIT delivers audio without synthesis, so it must charge the anon budget
    # exactly once (chars reserved, then KEPT because audio was delivered) — never
    # double-charged and never refunded. Mocking result_cache.get forces the hit, so
    # no model runs (valid `not synth`).
    from app import result_cache
    from app.quota import quota

    canned = b"ID3cached-mpeg-bytes"
    monkeypatch.setattr(result_cache, "get", lambda _k: canned)
    _override(Settings(api_keys="test-key", anon_chars_per_day=100_000, anon_burst=50, anon_rate_per_min=50))
    try:
        ip = client_ip(_request("testclient"))  # the key the gate uses under TestClient
        before = quota.usage(ip)[0]
        r = _client.post("/v1/audio/speech", json=_SPEECH)  # anon, cache hit -> no synth
        assert r.status_code == 200
        assert r.content == canned
        # Charged once for exactly the input length; not refunded, not doubled.
        assert quota.usage(ip)[0] - before == len(_SPEECH["input"])
    finally:
        _clear_override()


@pytest.mark.synth
def test_http_trusted_key_bypasses_rate_limit():
    # A valid key is TRUSTED: even with a zero bucket it is not rate-limited (it
    # would go on to synth, so we only assert it is NOT the 429 an anon would get).
    _override(Settings(anon_burst=0, anon_rate_per_min=0, api_keys="test-key"))
    try:
        r = _client.post(
            "/v1/audio/speech",
            headers={"Authorization": "Bearer test-key"},
            json={**_SPEECH, "input": "hi"},
        )
        assert r.status_code != 429
    finally:
        _clear_override()
