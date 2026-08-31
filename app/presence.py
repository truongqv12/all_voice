"""Live presence tracker: how many distinct client IPs are active right now.

Powers the public ``GET /v1/stats`` "đang dùng" (currently-using) gauge. Every
request touches the caller's IP; ``active_count(window_s)`` returns how many
distinct IPs were seen within the trailing window.

Purely in-memory and per-process — safe because the anon gate already pins the
app to a single worker (see ``main.py``). It is intentionally ephemeral: a
restart starts the gauge at 0 and it refills within one window as requests
arrive. No IP is ever exposed — only the aggregate count.
"""

from __future__ import annotations

import threading
import time

# Evict stale IPs only once the map grows past this, so the hot path (touch)
# stays allocation-free under normal load (mirrors quota.py's bounded map).
_EVICT_THRESHOLD = 10_000
# Upper bound past which an entry is certainly stale for any sane window, used
# to cap memory when active_count is never called (no frontend polling).
_HARD_STALE_S = 3600


class Presence:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}  # ip -> last_seen (monotonic clock)

    def touch(self, ip: str) -> None:
        """Record that ``ip`` is active as of now."""
        now = time.monotonic()
        with self._lock:
            self._seen[ip] = now
            if len(self._seen) > _EVICT_THRESHOLD:
                self._evict(now, _HARD_STALE_S)

    def active_count(self, window_s: int) -> int:
        """Distinct IPs seen within the trailing ``window_s`` seconds.

        Self-cleaning: anything older than the window is not "active" by
        definition, so we evict it here and return the remaining size.
        """
        now = time.monotonic()
        with self._lock:
            self._evict(now, window_s)
            return len(self._seen)

    def _evict(self, now: float, window_s: int) -> None:
        cutoff = now - window_s
        stale = [ip for ip, last in self._seen.items() if last < cutoff]
        for ip in stale:
            del self._seen[ip]

    def reset(self) -> None:
        """Drop all presence (test isolation)."""
        with self._lock:
            self._seen.clear()


#: Process-wide singleton.
presence = Presence()
