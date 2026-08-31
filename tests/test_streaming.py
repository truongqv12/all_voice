"""Phase 3 — long-read streaming: sentence split, disconnect stop, per-chunk
budget (#4), stream cap (#8). All `not synth`: a fake backend stands in for TTS so
the streaming control flow is tested without real synthesis.
"""

from __future__ import annotations

import asyncio
import io
import os

import av
import numpy as np
import pytest

os.environ.setdefault("API_KEYS", "test-key")

from app import streaming  # noqa: E402
from app.backends.base import AudioResult  # noqa: E402
from app.client_identity import Identity, Tier  # noqa: E402
from app.config import Settings  # noqa: E402
from app.limits import Overloaded, close_stream, open_stream, reset_state  # noqa: E402
from app.quota import Quota  # noqa: E402
from app.streaming import sentence_split, synth_stream  # noqa: E402


# --- sentence_split: deterministic, bounded chunks ---

def test_split_empty():
    assert sentence_split("") == []
    assert sentence_split("   ") == []


def test_split_packs_sentences_under_max_len():
    out = sentence_split("Hello world. Foo bar. Baz qux.", max_len=12)
    assert out == ["Hello world.", "Foo bar.", "Baz qux."]


def test_split_hard_splits_a_giant_token():
    out = sentence_split("x" * 50, max_len=20)
    assert out == ["x" * 20, "x" * 20, "x" * 10]
    assert all(len(c) <= 20 for c in out)


def test_split_breaks_long_sentence_on_clauses():
    text = "alpha beta, gamma delta, epsilon zeta, eta theta."
    out = sentence_split(text, max_len=20)
    assert all(len(c) <= 20 for c in out)
    assert len(out) >= 2


# --- fakes ---

class _FakeBackend:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.speeds: list[float] = []

    def synthesize(self, text, voice, speed=1.0, options=None):
        self.calls.append(text)
        self.speeds.append(speed)
        return AudioResult(pcm=np.zeros(4096, dtype=np.float32), sample_rate=48000)


class _FakeRequest:
    """`is_disconnected()` returns True from the `true_on`-th call onward."""

    def __init__(self, true_on: int | None = None) -> None:
        self.n = 0
        self.true_on = true_on

    async def is_disconnected(self) -> bool:
        self.n += 1
        return self.true_on is not None and self.n >= self.true_on


def _drive(gen):
    async def run():
        return [chunk async for chunk in gen]
    return asyncio.run(run())


# --- streaming end-to-end (fake backend) produces a decodable MP3 ---

def test_stream_yields_decodable_mp3():
    reset_state()
    backend = _FakeBackend()
    ident = Identity(ip="1.2.3.4", tier=Tier.TRUSTED)  # TRUSTED: skip budget
    req = _FakeRequest()
    chunks = ["One two three four.", "Five six seven eight.", "Nine ten."]
    out = _drive(synth_stream(
        backend=backend, voice="v", chunks=chunks, ident=ident,
        request=req, options={}, settings=Settings(),
    ))
    assert backend.calls == chunks  # every chunk synthesized
    data = b"".join(out)
    assert len(data) > 0
    with av.open(io.BytesIO(data)) as c:
        assert sum(f.samples for f in c.decode(audio=0)) > 0  # single-container stream decodes


def test_disconnect_stops_before_next_chunk():
    reset_state()
    backend = _FakeBackend()
    ident = Identity(ip="1.2.3.4", tier=Tier.TRUSTED)
    req = _FakeRequest(true_on=2)  # disconnect detected at the 2nd loop check
    chunks = ["First sentence.", "Second sentence.", "Third sentence."]
    _drive(synth_stream(
        backend=backend, voice="v", chunks=chunks, ident=ident,
        request=req, options={}, settings=Settings(),
    ))
    assert backend.calls == ["First sentence."]  # chunk 2+ never synthesized


def test_stream_forwards_native_speed_to_every_chunk():
    reset_state()
    backend = _FakeBackend()
    _drive(synth_stream(
        backend=backend, voice="v", chunks=["First.", "Second."],
        ident=Identity(ip="1.2.3.4", tier=Tier.TRUSTED), request=_FakeRequest(),
        options={}, settings=Settings(), speed=1.5,
    ))
    assert backend.speeds == [1.5, 1.5]


def test_budget_charged_only_for_yielded_chunks(tmp_path, monkeypatch):
    reset_state()
    test_quota = Quota(db_path=str(tmp_path / "q.db"))
    monkeypatch.setattr(streaming, "quota", test_quota)
    backend = _FakeBackend()
    ident = Identity(ip="9.9.9.9", tier=Tier.ANON)
    req = _FakeRequest(true_on=2)  # stop after the first chunk
    chunks = ["First sentence.", "Second sentence."]
    _drive(synth_stream(
        backend=backend, voice="v", chunks=chunks, ident=ident,
        request=req, options={}, settings=Settings(anon_chars_per_day=10_000),
    ))
    # Only the first chunk was reserved (commit-as-you-yield, #4).
    assert test_quota.usage("9.9.9.9")[0] == len("First sentence.")


def test_budget_stop_when_exhausted_mid_stream(tmp_path, monkeypatch):
    reset_state()
    test_quota = Quota(db_path=str(tmp_path / "q.db"))
    monkeypatch.setattr(streaming, "quota", test_quota)
    backend = _FakeBackend()
    ident = Identity(ip="8.8.8.8", tier=Tier.ANON)
    req = _FakeRequest()
    # Cap allows only the first ~chunk; the stream ends cleanly (no exception).
    chunks = ["First sentence.", "Second sentence.", "Third sentence."]
    _drive(synth_stream(
        backend=backend, voice="v", chunks=chunks, ident=ident,
        request=req, options={}, settings=Settings(anon_chars_per_day=len("First sentence.")),
    ))
    assert backend.calls == ["First sentence."]  # ran out of budget before chunk 2


# --- real synth over HTTP (VieNeu): the stream decodes as one continuous MP3 ---

@pytest.mark.synth
def test_http_stream_real_synth():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/audio/stream",
        headers={"Authorization": "Bearer test-key"},
        json={
            "model": "vieneu",
            "input": "Xin chào. Đây là bài đọc thử dài. Cảm ơn bạn đã lắng nghe.",
            "voice": "Trúc Ly",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert len(r.content) > 0
    with av.open(io.BytesIO(r.content)) as c:
        assert sum(f.samples for f in c.decode(audio=0)) > 0


# --- stream connection cap (#8) ---

def test_open_stream_cap_and_release():
    reset_state()
    s = Settings(anon_max_streams_per_ip=1)
    open_stream("ip", s)
    with pytest.raises(Overloaded):
        open_stream("ip", s)  # 2nd concurrent stream from same IP -> 429
    close_stream("ip")
    open_stream("ip", s)  # slot freed -> allowed again
    close_stream("ip")
