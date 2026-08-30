# Load-test & real E2E report — Public Share Readiness Stage 1

Status: **tooling delivered; live runs pending operator execution.**
Date started: 2026-08-30 · Scope: Phase 5 of `plans/260830-1054-public-share-readiness-stage1/`.

This is a stateful record, not evergreen docs. It captures the acceptance evidence for
*"1 CPU node does not crash or hang under abuse"* and the numbers chosen for the anon
gate. The **tooling** (k6 scenarios, `assert_stateful.py`, Playwright specs) is committed
and ready. The **runs** below require the deployed box + the operator's Cloudflare Tunnel
and a separate load machine, so their result cells are marked PENDING until executed.

## How to reproduce

Prereqs: box deployed per `docs/deployment.md` (API on `127.0.0.1:8123`, nginx on
`127.0.0.1:8080`, `ANON_ENABLED=true`, model warmed once). Run the abusive scenarios
**locally / from another LAN machine straight at nginx**, never at the public CF domain.

```bash
# throughput + liveness (scenario 1), sample resources alongside
uv run python scripts/loadtest/assert_stateful.py sample --seconds 150 --out throughput.csv &
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/throughput.js

BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/rate-limit.js     # scenario 2
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/budget.js         # scenario 3
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/queue.js          # scenario 4
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/stream-abuse.js   # scenario 6
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/asr-memdos.js     # scenario 7
BASE_URL=http://127.0.0.1:8080 k6 run scripts/loadtest/soak.js           # scenario 10 (45m)

uv run python scripts/loadtest/assert_stateful.py refund  --base http://127.0.0.1:8080  # scenario 5
uv run python scripts/loadtest/assert_stateful.py counter --base http://127.0.0.1:8080  # scenario 9
uv run python scripts/loadtest/assert_stateful.py spoof   --host <box-lan-ip>           # scenario 8 (from LAN)

# Cross-browser gapless over the real stack (dev/CI machine):
cd tests/e2e && npm install && npx playwright install
E2E_BASE_URL=https://voice.example.com npx playwright test stream-e2e.spec.ts
```

## Target box

i5-9400 · 6 cores · ~11 GB RAM · no GPU · 1 worker · `MAX_CONCURRENCY=1`.

## Drafted gate numbers under test (starting point)

Taken from `app/config.py` / `.env.example` at the start of Phase 5. Column "Final" is
filled only if measurement says the draft is wrong (Phase 5 step 4).

| Setting | Draft | Final | Note |
|---|---|---|---|
| `anon_rate_per_min` | 10 | _pending_ | |
| `anon_burst` | 10 | _pending_ | new IPs seed at full burst (documented deviation, see below) |
| `anon_chars_per_day` | 50000 | _pending_ | |
| `anon_audio_seconds_per_day` | 1800 | _pending_ | |
| `anon_max_chars_buffered` | 1200 | _pending_ | over → 400, points to /v1/audio/stream |
| `anon_max_chars_stream` | 20000 | _pending_ | revisit if CF 524 appears |
| `anon_max_audio_seconds` | 300 | _pending_ | over → 413 before CPU |
| `anon_max_concurrent_per_ip` | 2 | _pending_ | |
| `anon_max_streams_per_ip` | 2 | _pending_ | |
| `max_queue_waiters` | 20 | _pending_ | |
| `request_timeout_s` | 90 | _pending_ | slot-wait ceiling; never hang |

> **Cold-start bucket seeding (deviation from plan literal):** new IPs seed the token
> bucket at **full burst** for good first-request UX. The abuse backstops are the
> persistent daily SQLite budget and the admission queue (immediate 429, no hang), not
> an empty starting bucket. Confirm under scenarios 2 + 10 that this does not let a
> fresh-IP flood hurt the box; adjust `anon_burst` if it does.

## Scenario results (map to red-team findings)

| # | Scenario | Tool | Expected | Result |
|---|---|---|---|---|
| 1 | Concurrent legit TTS | throughput.js + sample | no OOM/hang; `/v1/models` p95 < 500ms during synth; p50/p95 recorded | _pending_ |
| 2 | Exceed rate limit | rate-limit.js | 429 immediately, OpenAI envelope | _pending_ |
| 3 | Exceed daily budget (#cost) | budget.js | 429 after char cap, resets next UTC day | _pending_ |
| 4 | Queue saturation | queue.js | overflow 429 Overloaded now; none > request_timeout_s | _pending_ |
| 5 | Refund net-zero (#4) | assert_stateful refund | charged chars == 0 after failed requests | _pending_ |
| 6 | Stream cap (#8) | stream-abuse.js + sample | excess streams 429; RAM flat | _pending_ |
| 7 | ASR mem-DoS (#7) | asr-memdos.js + sample | shed by header/size before body work; RAM bounded | _pending_ |
| 8 | IP spoof / loopback (#1) | assert_stateful spoof (from LAN) | :8123 + :8080 refused off-box | _pending_ |
| 9 | Counter leak (#12) | assert_stateful counter | IP still served after a failure burst | _pending_ |
| 10 | Soak 30–60′ (#9) | soak.js + sample | no RAM leak; `data/cache` ≤ max_mb; no crash-loop | _pending_ |

Peak resource use (fill from `sample` output): CPU peak ____% · RAM peak ____ MB · swap peak ____ MB.

## Real E2E over Cloudflare (from an external 4G client)

Manual checklist (Phase 5 part A) — run against `https://voice.example.com`:

- [ ] Discovery `GET /v1/voices` → 200, presets (+ clones) visible, no key.
- [ ] Buffered TTS with no `Authorization` → audio plays.
- [ ] Streaming long text → mp3 flows progressively, plays on a real `<audio>`.
- [ ] App log shows the **real client IP** from `CF-Connecting-IP` (not `127.0.0.1`).
- [ ] Cross-browser gapless (Chromium/Firefox/WebKit) via `stream-e2e.spec.ts` → green.
- [ ] Edge WAF/rate-rule blocks a flood at the CF edge (block page), before the app gate.

## CF 524 decision (open question)

Stream a **very long** passage (playback > 100s) over the CF domain and time it.

- Result: _pending_ (no 524 / got 524).
- **Decision:** _pending_ — if no 524, keep streaming as-is. If 524 appears, lower
  `anon_max_chars_stream` now and schedule the async-job path for a later stage
  (documented as an open question, not a Stage-1 blocker).

## Sign-off

- [ ] Box did not OOM or hang under the full scenario set.
- [ ] Every over-limit path returned 429/400/413 immediately (never a hang).
- [ ] Refund net-zero, counters released, RAM flat on stream + soak.
- [ ] Real E2E over CF works with correct client IP; gapless confirmed cross-browser.
- [ ] Gate numbers finalized (table above) with reasons; config updated if drifted.
