---
title: Public share readiness Stage 1
date: 2026-08-30
summary: "Opened TTS/ASR publicly (no login) behind nginx + Cloudflare Tunnel on one CPU box with a real-cost abuse gate, result cache, and long-read MP3 streaming"
---

# Public share readiness Stage 1

## What shipped

Opened the OpenAI-compatible TTS/ASR gateway to **anonymous public users (no login)** on a single i5-9400 / 6-core / 11GB / no-GPU box behind **nginx + Cloudflare Tunnel**, engineered so one CPU node does not crash or hang under abuse. Delivered across 5 phases on branch `feat/public-share-readiness-stage1` (5 focused commits).

- **Two-tier access:** no key = ANON (gated), valid key = TRUSTED (bypass). Discovery (`/v1/voices`, `/v1/models`, previews) public; clone CRUD still key-only.
- **Real-cost gate:** self-protects by characters (TTS) / seconds of audio (ASR), not request counting. In-memory token-bucket rate limit + SQLite per-IP/day budget (WAL, fail-closed) + admission control (per-IP concurrency + bounded queue + slot-wait timeout → 429 immediately, never hang).
- **Streaming long reads** (`POST /v1/audio/stream`): sentence split, budget committed per yielded chunk, disconnect stops at next sentence.
- **Result cache** for buffered TTS (SHA1 key, disk, background LRU).
- **Edge/deploy:** loopback bind default (fail-closed), nginx example (buffering off, body cap, CF-Connecting-IP passthrough), Cloudflare Tunnel guide + WAF checklist, systemd CPU cap + crash-loop backoff + refuse-start on anon+workers>1, vanilla test UI.
- **Load/stress tooling:** k6 scenarios + stateful Python assertions (refund, reachability, counter, /proc sampler) + Playwright cross-browser e2e; report scaffold. Live runs over the CF domain are operator tasks.

## Key technical decisions

- **Gapless streaming by construction:** chose ONE continuous `av` MP3 container fed frame-by-frame (write-only non-seekable sink skips the Xing header) instead of per-sentence file concatenation — closes the "gapless MP3" risk without a browser-dependent spike.
- **Loopback-gate for IP trust:** `CF-Connecting-IP` trusted only when the socket peer is loopback (nginx), so a direct caller can't spoof its IP to dodge the budget. IPv6 normalized to /64 against address-rotation.
- **Fail-closed everywhere:** DB error during a budget reserve → reject (never fall open); host defaults to 127.0.0.1; app refuses to start with anon + workers>1 (the gate is per-process in-memory + single-writer SQLite).
- **Reserve-then-refund** budget so any non-delivery (429/400/timeout/disconnect) is net-zero; admission counters released in `finally` on every path incl. cancellation.
- **CPU cap belongs in systemd:** onnxruntime torch-free may ignore `OMP_NUM_THREADS`, so the real lever is cgroup `CPUQuota`/`AllowedCPUs` in the unit file; the OMP env is defence in depth.

## Deviation from plan (documented)

New IPs seed the rate token-bucket at **full burst** (not empty as the phase text said) for good first-request UX. Judged sound in code review: the durable backstops are the persistent daily SQLite budget + the admission queue (immediate 429, no hang) + systemd restart backoff — every safety-critical property is preserved; only per-IP cold-start rate smoothing is weaker.

## Verification

- Fast suite `uv run pytest -m "not synth"` → **103 passed** (added a cache-hit + budget-charged-once integration test).
- Live smoke: API bound `127.0.0.1` only (hidden from LAN), discovery public (200 no key), clone CRUD 401, real IP logged.
- Independent code review: DONE_WITH_CONCERNS, no blocking defects, all 14 accepted red-team findings verified closed. Fixed the surfaced items: stale OpenAPI auth description, dead `inference_threads` config field, macOS `0.0.0.0` hint.

## Pending (operator / next)

- Real E2E from an external client over the live Cloudflare domain; k6 stress + soak runs; finalize the drafted gate numbers from measurements — all need the operator's CF Tunnel + a separate load box. Tooling + report scaffold ready.
- Open question **CF 524** on >100s streams: measure over CF; if it appears, lower `anon_max_chars_stream` and schedule async-job (later stage).
- Branch not pushed; no PR opened (per request).

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
