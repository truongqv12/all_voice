#!/usr/bin/env python3
"""Stateful load-test assertions the k6 scripts can't do well, plus a CPU/RAM sampler.

k6 measures throughput and status codes; these checks need to read server-side state
(the SQLite budget) or reason about per-IP counters across requests. Run them against
a LIVE server — normally through nginx on the box (so CF-Connecting-IP is trusted on
the loopback hop), from the box itself or another LAN machine.

Covers the red-team scenarios k6 leaves out:

  refund   (#4)  reserve-then-refund is net-zero: fire requests that fail AFTER the
                 budget is reserved (bad `style` -> 400) from a fresh IP, then read
                 data/quota.db and assert that IP's `chars` for today is 0.
  spoof    (#1)  loopback bind + firewall: probe whether :8124 (API) and :8123 (nginx)
                 are reachable on a target host. From the LAN both must REFUSE — only
                 cloudflared reaches them. (The loopback-gate that ignores a spoofed
                 CF-Connecting-IP from a non-loopback peer is unit-tested in
                 tests/test_gate.py, which can fake the socket peer.)
  counter  (#12) per-IP concurrency isn't leaked: hammer one IP with failing requests
                 (bad `style` -> 400), then confirm that IP is STILL served afterward
                 (a follow-up request is not stuck at 429 Overloaded).

  sample         poll /proc for CPU%, RAM, and swap for N seconds (optionally to CSV).
                 Run this alongside any k6 scenario to catch OOM / swap / a pinned box.

Usage:
  python scripts/loadtest/assert_stateful.py sample --seconds 90 --interval 2 --out cpu.csv
  python scripts/loadtest/assert_stateful.py refund  --base http://127.0.0.1:8123 --db data/quota.db
  python scripts/loadtest/assert_stateful.py counter --base http://127.0.0.1:8123
  python scripts/loadtest/assert_stateful.py spoof   --host 192.168.1.50   # from another LAN machine

Needs httpx (already a project dep): run with `uv run python scripts/loadtest/assert_stateful.py ...`.
"""

from __future__ import annotations

import argparse
import csv
import socket
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

MODEL = "vieneu"
VOICE = "Trúc Ly"


def _speech(base: str, ip: str, *, style: str | None = None, input_len: int = 200,
            timeout: float = 120.0) -> httpx.Response:
    body = {"model": MODEL, "input": "a" * input_len, "voice": VOICE}
    if style is not None:
        body["style"] = style
    return httpx.post(
        f"{base}/v1/audio/speech",
        json=body,
        headers={"CF-Connecting-IP": ip},
        timeout=timeout,
    )


# --- refund (#4) ------------------------------------------------------------

def cmd_refund(args: argparse.Namespace) -> int:
    ip = args.ip
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = args.count
    print(f"[refund] firing {n} bad-style requests from {ip} (expect 400, budget refunded)")
    codes: dict[int, int] = {}
    for _ in range(n):
        r = _speech(args.base, ip, style="__definitely_invalid__", input_len=args.input_len)
        codes[r.status_code] = codes.get(r.status_code, 0) + 1
    print(f"[refund] status codes: {codes}")

    chars = _usage_chars(args.db, ip, day)
    if chars is None:
        print(f"[refund] no usage row for {ip} on {day} -> chars effectively 0")
        chars = 0
    print(f"[refund] chars charged today for {ip}: {chars}")
    if chars == 0:
        print("[refund] PASS: reserve-then-refund is net-zero (#4).")
        return 0
    print(f"[refund] FAIL: expected 0 charged after failed requests, got {chars}.")
    return 1


def _usage_chars(db_path: str, ip: str, day: str) -> int | None:
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        print(f"[refund] cannot open {db_path}: {exc}", file=sys.stderr)
        return None
    try:
        row = conn.execute(
            "SELECT chars FROM usage WHERE ip=? AND day=?", (ip, day)
        ).fetchone()
    except sqlite3.OperationalError:
        return None  # table not created yet -> nothing charged
    finally:
        conn.close()
    return row[0] if row else None


# --- counter leak (#12) -----------------------------------------------------

def cmd_counter(args: argparse.Namespace) -> int:
    ip = args.ip
    m = args.count
    print(f"[counter] firing {m} concurrent bad-style requests from {ip} (expect 400s)")
    with ThreadPoolExecutor(max_workers=m) as pool:
        results = list(pool.map(
            lambda _: _speech(args.base, ip, style="__definitely_invalid__").status_code,
            range(m),
        ))
    print(f"[counter] error-batch codes: {_hist(results)}")
    time.sleep(1.0)  # let any in-flight work drain

    # If per-IP concurrency were leaked, this IP would now be permanently Overloaded.
    follow = _speech(args.base, ip, style=None, input_len=200)
    print(f"[counter] follow-up request from {ip}: {follow.status_code}")
    if follow.status_code == 429 and _is_overloaded(follow):
        print("[counter] FAIL: IP stuck at 429 Overloaded -> concurrency counter leaked (#12).")
        return 1
    print("[counter] PASS: IP still served after a burst of failures (counter released).")
    return 0


def _is_overloaded(r: httpx.Response) -> bool:
    try:
        return r.json().get("error", {}).get("code") == "overloaded"
    except Exception:
        return False


# --- spoof / reachability (#1) ---------------------------------------------

def cmd_spoof(args: argparse.Namespace) -> int:
    host = args.host
    print(f"[spoof] probing TCP reachability of {host}:8124 (API) and {host}:8123 (nginx)")
    api = _reachable(host, 8124, args.connect_timeout)
    edge = _reachable(host, 8123, args.connect_timeout)
    print(f"[spoof] {host}:8124 reachable={api}   {host}:8123 reachable={edge}")

    loopback = host in ("127.0.0.1", "::1", "localhost")
    if loopback:
        print("[spoof] (localhost) reachability here is EXPECTED — the gate binds loopback.")
        print("[spoof] Re-run from another LAN machine with --host <box-ip>; both must be refused.")
        return 0
    if not api and not edge:
        print("[spoof] PASS: neither port reachable from the LAN — only cloudflared gets in (#1).")
        return 0
    print("[spoof] FAIL: a port is reachable from the LAN. Bind loopback + `ufw deny 8124/tcp`.")
    return 1


def _reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# --- CPU / RAM / swap sampler ----------------------------------------------

def cmd_sample(args: argparse.Namespace) -> int:
    writer = None
    fh = None
    if args.out:
        fh = open(args.out, "w", newline="")
        writer = csv.writer(fh)
        writer.writerow(["t", "cpu_pct", "mem_used_mb", "mem_pct", "swap_used_mb"])
    print(f"[sample] {args.seconds}s @ {args.interval}s  (Ctrl-C to stop)")
    prev = _cpu_times()
    peak_cpu = peak_mem = peak_swap = 0.0
    end = time.time() + args.seconds
    try:
        while time.time() < end:
            time.sleep(args.interval)
            cur = _cpu_times()
            cpu = _cpu_pct(prev, cur)
            prev = cur
            mem_used, mem_pct, swap_used = _mem()
            peak_cpu = max(peak_cpu, cpu)
            peak_mem = max(peak_mem, mem_used)
            peak_swap = max(peak_swap, swap_used)
            line = f"cpu={cpu:5.1f}%  mem={mem_used:7.0f}MB ({mem_pct:4.1f}%)  swap={swap_used:6.0f}MB"
            print("[sample] " + line)
            if writer:
                writer.writerow([f"{time.time():.0f}", f"{cpu:.1f}", f"{mem_used:.0f}",
                                 f"{mem_pct:.1f}", f"{swap_used:.0f}"])
                fh.flush()
    except KeyboardInterrupt:
        pass
    finally:
        if fh:
            fh.close()
    print(f"[sample] PEAK cpu={peak_cpu:.1f}%  mem={peak_mem:.0f}MB  swap={peak_swap:.0f}MB")
    if peak_swap > args.swap_alarm_mb:
        print(f"[sample] WARN: swap peaked at {peak_swap:.0f}MB (> {args.swap_alarm_mb}MB) — box under memory pressure.")
    return 0


def _cpu_times() -> tuple[int, int]:
    with open("/proc/stat") as f:
        parts = f.readline().split()[1:]
    vals = list(map(int, parts))
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return sum(vals), idle


def _cpu_pct(prev: tuple[int, int], cur: tuple[int, int]) -> float:
    dt = cur[0] - prev[0]
    di = cur[1] - prev[1]
    return 0.0 if dt <= 0 else max(0.0, 100.0 * (dt - di) / dt)


def _mem() -> tuple[float, float, float]:
    info: dict[str, float] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v, *_ = line.replace(":", "").split()
            info[k] = float(v)  # kB
    total = info.get("MemTotal", 0) / 1024
    avail = info.get("MemAvailable", 0) / 1024
    used = total - avail
    pct = 100.0 * used / total if total else 0.0
    swap_total = info.get("SwapTotal", 0) / 1024
    swap_free = info.get("SwapFree", 0) / 1024
    return used, pct, swap_total - swap_free


def _hist(codes: list[int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for c in codes:
        out[c] = out.get(c, 0) + 1
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("refund", help="scenario 5: reserve-then-refund is net-zero (#4)")
    pr.add_argument("--base", default="http://127.0.0.1:8123")
    pr.add_argument("--db", default="data/quota.db")
    pr.add_argument("--ip", default="198.51.100.55")
    pr.add_argument("--count", type=int, default=15)
    pr.add_argument("--input-len", type=int, default=200)
    pr.set_defaults(func=cmd_refund)

    pc = sub.add_parser("counter", help="scenario 9: per-IP concurrency not leaked (#12)")
    pc.add_argument("--base", default="http://127.0.0.1:8123")
    pc.add_argument("--ip", default="198.51.100.66")
    pc.add_argument("--count", type=int, default=20)
    pc.set_defaults(func=cmd_counter)

    ps = sub.add_parser("spoof", help="scenario 8: :8124/:8123 unreachable from the LAN (#1)")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--connect-timeout", type=float, default=3.0)
    ps.set_defaults(func=cmd_spoof)

    pp = sub.add_parser("sample", help="poll /proc for CPU/RAM/swap")
    pp.add_argument("--seconds", type=int, default=60)
    pp.add_argument("--interval", type=float, default=2.0)
    pp.add_argument("--out", default=None, help="write a CSV time series here")
    pp.add_argument("--swap-alarm-mb", type=float, default=200.0)
    pp.set_defaults(func=cmd_sample)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
