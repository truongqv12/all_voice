"""Per-IP abuse gate: in-memory token-bucket rate limit + SQLite daily budget.

Two independent limiters keyed by the trusted client IP (see `client_identity`):

- **Rate** (`allow_rate`): a token bucket held purely in memory — cheap, per-process
  (fine on the single worker anon requires). Smooths bursts.
- **Budget** (`reserve_chars` / `reserve_audio`): a per-IP, per-UTC-day tally in
  SQLite, so it survives restarts (the durable abuse backstop). Billed in the units
  of real CPU cost — characters for TTS, milliseconds of audio for ASR.

Design notes tied to the red-team review:

- **Reserve-then-refund** (#4): callers reserve the cost up front and refund it on
  any path that does NOT deliver audio (429/400/timeout/disconnect), so a rejected
  request is net-zero against the daily budget.
- **Fail-closed** (#15): the DB is opened WAL + `busy_timeout` immediately (not
  lazily on first lock), and any `sqlite3.OperationalError` during a *reserve*
  raises `QuotaExceeded` — we never fall open and let an unmetered request through.
  Refunds swallow infra errors (best-effort; failing to refund only over-charges).
- **Off the event loop**: SQLite calls are synchronous; routers run them via
  `anyio.to_thread.run_sync` so a busy DB never blocks the loop.
- **Bounded map** (#9): the bucket map evicts entries idle past `ip_map_ttl_s`.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from .config import Settings, get_settings
from .limits import GateError


class RateLimited(GateError):
    """Token bucket empty for this IP -> 429."""

    code = "rate_limit_exceeded"


class QuotaExceeded(GateError):
    """Daily cost budget exhausted (or the budget store is unavailable) -> 429."""

    code = "quota_exceeded"


# Evict idle IPs from the bucket map only once it grows past this, to keep the
# common path allocation-free.
_EVICT_THRESHOLD = 10_000


class Quota:
    def __init__(self, db_path: str | None = None) -> None:
        self._bucket_lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last_refill)
        self._db_lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        # (total_distinct_ips, computed_at_monotonic) — cache for total_users().
        self._total_users_cache: tuple[int, float] | None = None
        # None -> resolve from settings at connect time (production singleton);
        # an explicit path lets tests point at a throwaway DB.
        self._db_path = db_path

    # --- rate limit (in-memory token bucket) ---------------------------------

    def allow_rate(self, ip: str, settings: Settings | None = None) -> None:
        """Consume one token for `ip`; raise `RateLimited` if the bucket is empty."""
        s = settings or get_settings()
        rate, burst = s.anon_rate_per_min, s.anon_burst
        now = time.monotonic()
        with self._bucket_lock:
            self._maybe_evict(now, s)
            tokens, last = self._buckets.get(ip, (float(burst), now))
            # New IPs seed at full burst: good UX, and abuse is caught by the
            # persistent daily budget + the admission queue (429 immediately, no
            # hang) rather than by starving fresh clients.
            tokens = min(float(burst), tokens + (now - last) * rate / 60.0)
            if tokens < 1.0:
                self._buckets[ip] = (tokens, now)
                raise RateLimited("Rate limit exceeded. Please slow down.")
            self._buckets[ip] = (tokens - 1.0, now)

    def _maybe_evict(self, now: float, s: Settings) -> None:
        if len(self._buckets) < _EVICT_THRESHOLD:
            return
        ttl = s.ip_map_ttl_s
        stale = [ip for ip, (_t, last) in self._buckets.items() if now - last > ttl]
        for ip in stale:
            del self._buckets[ip]

    # --- daily budget (SQLite) -----------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        path = Path(self._db_path or get_settings().quota_db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        # WAL + busy_timeout from the start (#15): don't wait for the first lock
        # to harden the DB. synchronous=NORMAL is safe under WAL and much cheaper.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS usage ("
            "ip TEXT, day TEXT, chars INTEGER DEFAULT 0, audio_ms INTEGER DEFAULT 0, "
            "PRIMARY KEY (ip, day))"
        )
        conn.commit()
        self._conn = conn
        return conn

    @staticmethod
    def _today() -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _reserve(self, ip: str, column: str, amount: int, cap: int) -> None:
        if amount <= 0:
            return
        day = self._today()
        with self._db_lock:
            try:
                conn = self._connect()
                row = conn.execute(
                    f"SELECT {column} FROM usage WHERE ip=? AND day=?", (ip, day)
                ).fetchone()
                used = row[0] if row else 0
                if used + amount > cap:
                    raise QuotaExceeded("Daily budget exceeded. Try again tomorrow.")
                conn.execute(
                    f"INSERT INTO usage (ip, day, {column}) VALUES (?, ?, ?) "
                    f"ON CONFLICT(ip, day) DO UPDATE SET {column}={column}+?",
                    (ip, day, amount, amount),
                )
                conn.commit()
            except sqlite3.OperationalError as exc:  # fail-CLOSED (#15)
                raise QuotaExceeded("Budget store temporarily unavailable.") from exc

    def _refund(self, ip: str, column: str, amount: int) -> None:
        if amount <= 0:
            return
        day = self._today()
        with self._db_lock:
            try:
                conn = self._connect()
                conn.execute(
                    f"UPDATE usage SET {column}=MAX(0, {column}-?) WHERE ip=? AND day=?",
                    (amount, ip, day),
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass  # best-effort: a failed refund only over-charges, never opens

    def reserve_chars(self, ip: str, n: int, settings: Settings | None = None) -> None:
        self._reserve(ip, "chars", n, (settings or get_settings()).anon_chars_per_day)

    def refund_chars(self, ip: str, n: int) -> None:
        self._refund(ip, "chars", n)

    def reserve_audio(self, ip: str, ms: int, settings: Settings | None = None) -> None:
        cap = (settings or get_settings()).anon_audio_seconds_per_day * 1000
        self._reserve(ip, "audio_ms", ms, cap)

    def refund_audio(self, ip: str, ms: int) -> None:
        self._refund(ip, "audio_ms", ms)

    def usage(self, ip: str) -> tuple[int, int]:
        """(chars, audio_ms) used today for `ip` — for tests / introspection."""
        with self._db_lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT chars, audio_ms FROM usage WHERE ip=? AND day=?", (ip, self._today())
            ).fetchone()
        return (row[0], row[1]) if row else (0, 0)

    def total_users(self, ttl_s: float = 60.0) -> int:
        """Distinct IPs that have ever used the service (any day in the usage
        table) — the "đã dùng" figure for the public stats gauge.

        Cached for ``ttl_s`` seconds: ``COUNT(DISTINCT ip)`` scans the table and
        this feeds a frequently-polled endpoint, so we don't recompute per hit.
        A DB error is non-fatal (a gauge must never take the endpoint down): we
        serve the last known value, or 0 if we have none yet.
        """
        now = time.monotonic()
        with self._db_lock:
            cached = self._total_users_cache
            if cached is not None and now - cached[1] < ttl_s:
                return cached[0]
            try:
                conn = self._connect()
                row = conn.execute("SELECT COUNT(DISTINCT ip) FROM usage").fetchone()
                total = int(row[0]) if row and row[0] is not None else 0
            except sqlite3.OperationalError:
                return cached[0] if cached is not None else 0
            self._total_users_cache = (total, now)
            return total

    def reset(self) -> None:
        """Drop all in-memory buckets + close the DB handle (test isolation)."""
        with self._bucket_lock:
            self._buckets.clear()
        with self._db_lock:
            self._total_users_cache = None
            if self._conn is not None:
                self._conn.close()
                self._conn = None


#: Process-wide singleton.
quota = Quota()
