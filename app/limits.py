"""Concurrency guard + admission control for CPU-bound jobs (TTS + ASR).

`synth_semaphore` caps how many synth/transcribe jobs run at once (they share one
MAX_CONCURRENCY budget). `admit()` layers admission control on top so an overloaded
box rejects fast (429) instead of queueing without bound:

- **Per-IP concurrency** (`anon_max_concurrent_per_ip`): one IP can't hold every slot.
- **Bounded queue** (`max_queue_waiters`): once that many callers are already
  waiting for a slot, the next caller is rejected immediately — never an unbounded
  wait that pins RAM on a swap-poor box.
- **Wait timeout** (`request_timeout_s`, #3): bounds the wait *for a slot*, not the
  synthesis itself — a thread already running `to_thread.run_sync` can't be
  cancelled, so we cap load by refusing at admission, not by killing work in flight.

Every counter is released in a `finally` around the `yield` (#12), so any exit —
success, timeout, or an exception inside the body — returns the slot.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

import anyio

from .config import Settings, get_settings


class GateError(Exception):
    """Base for gate rejections rendered as HTTP 429 with the OpenAI envelope.

    Subclasses set `code`; the message is the exception's string. Shared by
    `Overloaded` here and `RateLimited`/`QuotaExceeded` in `app.quota`."""

    status_code = 429
    code = "rate_limit_exceeded"


class Overloaded(GateError):
    """Server at capacity: per-IP concurrency hit, queue full, or slot-wait timed
    out. Rejected immediately so the box never hangs."""

    code = "server_overloaded"


# Caps concurrent CPU-bound jobs so we don't oversubscribe cores. Shared by TTS
# synthesis and ASR transcription from one MAX_CONCURRENCY budget.
synth_semaphore = anyio.Semaphore(get_settings().max_concurrency)


class _GateState:
    """Mutable admission counters, guarded by one lock (single-worker process)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.ip_conc: dict[str, int] = {}   # in-flight synth jobs per IP
        self.waiters = 0                     # callers currently blocked on a slot
        self.streams: dict[str, int] = {}    # open /v1/audio/stream connections per IP


_state = _GateState()


@asynccontextmanager
async def admit(ip: str, settings: Settings | None = None):
    """Admit one CPU-bound job for `ip` or raise `Overloaded` immediately.

    On entry: reject if the IP is at its concurrency cap or the queue is full.
    Otherwise wait (bounded by `request_timeout_s`) for a synth slot, run the body,
    and release everything on the way out."""
    s = settings or get_settings()
    with _state.lock:
        if _state.ip_conc.get(ip, 0) >= s.anon_max_concurrent_per_ip:
            raise Overloaded("Too many concurrent requests from your address.")
        if _state.waiters >= s.max_queue_waiters:
            raise Overloaded("Server is busy. Please retry shortly.")
        _state.ip_conc[ip] = _state.ip_conc.get(ip, 0) + 1
        _state.waiters += 1

    acquired = False
    try:
        try:
            with anyio.fail_after(s.request_timeout_s):
                await synth_semaphore.acquire()
            acquired = True
        except TimeoutError as exc:
            raise Overloaded("Timed out waiting for a synthesis slot.") from exc
        finally:
            with _state.lock:
                _state.waiters -= 1
        yield
    finally:
        if acquired:
            synth_semaphore.release()
        with _state.lock:
            left = _state.ip_conc.get(ip, 0) - 1
            if left > 0:
                _state.ip_conc[ip] = left
            else:
                _state.ip_conc.pop(ip, None)


def open_stream(ip: str, settings: Settings | None = None) -> None:
    """Reserve one streaming connection for `ip` or raise `Overloaded` (#8). Held
    for the whole connection; pair with `close_stream` in a `finally`."""
    s = settings or get_settings()
    with _state.lock:
        if _state.streams.get(ip, 0) >= s.anon_max_streams_per_ip:
            raise Overloaded("Too many open streams from your address.")
        _state.streams[ip] = _state.streams.get(ip, 0) + 1


def close_stream(ip: str) -> None:
    with _state.lock:
        left = _state.streams.get(ip, 0) - 1
        if left > 0:
            _state.streams[ip] = left
        else:
            _state.streams.pop(ip, None)


def reset_state() -> None:
    """Clear admission counters (test isolation). Does not touch the semaphore."""
    with _state.lock:
        _state.ip_conc.clear()
        _state.streams.clear()
        _state.waiters = 0
