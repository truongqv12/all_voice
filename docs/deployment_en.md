# Deployment

Self-hosted on Linux/macOS. The application is a Python service managed by `uv`; no database needed, no system FFmpeg required (PyAV is included), no manual Python installation needed (`uv` automatically fetches Python 3.12).

## Platform
Self-managed server (VPS/bare-metal). Runs in the background via **systemd** on Linux.

## Deployment Commands (New Machine)

```bash
git clone <repo> all-voice && cd all-voice   # or copy the source (with uv.lock, .python-version)
bash deploy/setup.sh                         # installs uv + deps (including PyTorch for voice cloning)
nano .env                                    # set your real API_KEYS, adjust PORT/DEVICE if needed
sudo bash deploy/install-service.sh          # run in the background as a system service (Linux)
```

No voice cloning needed (lighter, doesn't install PyTorch): `CLONE=0 bash deploy/setup.sh`.

The VieNeu model (~313MB) is downloaded automatically on the **first synth request** to `~/.cache/huggingface/hub` (change the location with `HF_HOME` in `.env`).

## Scripts in `deploy/`

| File | Task |
|---|---|
| `deploy/setup.sh` | Installs `uv`, runs `uv sync --frozen [--extra clone]`, creates `.env` + `logs/`. Idempotent. |
| `deploy/install-service.sh` | Generates a systemd unit based on actual path/user/PORT, and runs `enable --now`. Linux only, requires `sudo`. |

## Environment Variables (`.env`)

`API_KEYS` (must be changed from `dev-key`) · `DEVICE` (cpu/cuda/auto) ·
`DEFAULT_BACKEND` · `MAX_CONCURRENCY` · `VOICES_DIR` · `HOST` (**default `127.0.0.1`** — loopback, hidden behind nginx; see "Public via Cloudflare Tunnel") · `PORT` (default 8124) · `LOG_LEVEL` · `LOG_DIR` · `HF_HOME`.

Anonymous public access (anon gate) + streaming + result caching variables:
`ANON_ENABLED`, `ANON_RATE_PER_MIN`, `ANON_BURST`, `ANON_CHARS_PER_DAY`, `ANON_AUDIO_SECONDS_PER_DAY`, `ANON_MAX_*`, `MAX_QUEUE_WAITERS`, `REQUEST_TIMEOUT_S`, `INFERENCE_THREADS`, `ASR_CPU_THREADS`, `RESULT_CACHE_*` — full list + defaults are in `.env.example` and `app/config.py`. See the "Public via Cloudflare Tunnel" section below.

Optional engine variables (full list + defaults in `app/config.py`, README "Engines" section):
`ENABLE_KOKORO` · `KOKORO_MODEL_PATH` · `KOKORO_VOICES_PATH` · `KOKORO_DEFAULT_VOICE` · `ENABLE_VOICEVOX` · `VOICEVOX_DICT_DIR` · `VOICEVOX_VVM_DIR` · `VOICEVOX_ONNXRUNTIME` · `VOICEVOX_SPEAKER_ALLOWLIST`.

Voice preview configuration: `PREVIEWS_DIR` (default `data/previews`, **can be deleted** — auto-recreated) · `PREVIEW_WARM_ON_STARTUP` (warms default backend + clones at startup, runs in background) · `PREVIEW_CONCURRENCY` (CPU budget **specifically** for previews, separate from `MAX_CONCURRENCY` so it doesn't steal CPU from speech/ASR requests; default 1) · `PREVIEW_TEXT_VI` / `PREVIEW_TEXT_EN` / `PREVIEW_TEXT_JA` (change preview text, leave blank for defaults). With `WORKERS≥2`, previews are saved with **one sidecar file per audio** (`{slug}.mp3.json`) to avoid shared manifest conflicts.

## English Engine (Kokoro) & Japanese Engine (VOICEVOX)

Optional, separate from the base install. If an engine is enabled but **assets are not downloaded**, the backend will safely skip it (won't break startup); disable entirely with `ENABLE_KOKORO=false` / `ENABLE_VOICEVOX=false`.

- **English (Kokoro):** requires system package **`espeak-ng`** for G2P — `sudo apt-get install -y espeak-ng`. Then `uv sync --extra en` + `bash scripts/fetch-kokoro.sh` (int8 model **~88 MB** + voices downloaded to `models/kokoro/`).
- **Japanese (VOICEVOX):** `uv sync --extra ja` + `bash scripts/fetch-voicevox.sh` (installs `voicevox_core` wheel from GitHub release + downloads OpenJTalk dict + VVM to `models/voicevox/`). **Credit:** Character attribution is required when publishing audio (see README).
- **RAM / lazy-load:** each enabled engine only loads its model on the **first request** for that language; VOICEVOX loads **each VVM per style** when needed → startup does not bloat RAM. Still recommended to **keep 1 worker** (each worker holds its own model copy). Disk: `models/` is not committed (`.gitignore`), total size depends on enabled engines.

## Operating the Service (Linux)

```bash
systemctl status all-voice            # status
journalctl -u all-voice -f            # realtime logs (or: tail -f logs/server.log)
sudo systemctl restart all-voice      # restart
sudo systemctl disable --now all-voice # stop + disable autostart
```

- The service automatically restarts on crash (`Restart=always`) and on machine reboot.
- **1 default worker** (change with `WORKERS=N sudo bash deploy/install-service.sh`). Each worker loads **its own TTS + ASR model copy** into RAM, while inference is **CPU-bound** (CTranslate2/torch uses all cores) — adding workers only consumes more RAM without increasing throughput on a single node machine. Only increase `WORKERS` when you have many free CPU/RAM and need true parallel load.
- **Cloned voices when running multiple workers (`WORKERS≥2`):** listing/deleting voices uses a shared `registry.json` (store reads from disk every time) so it can be deleted on any worker. But a cloned voice enrolled for **synth** stays in the RAM of **the worker that created it** until restart — other workers that don't have it will fallback to the first preset. If you want all workers to immediately synth a newly created voice: `sudo systemctl restart all-voice` (re-enrolls all from `registry.json` at startup). With the default 1 worker, this is not an issue.
- `logs/server.log` catches stdout+stderr (captures uvicorn logs and native segfaults); `logs/app.log` is the rotating application log (startup/request/synth/500 errors).

## Public via Cloudflare Tunnel + nginx (API hidden at localhost)

Expose the service to the internet for **free users without login**, running on a **1 CPU machine** without crashing/hanging under abuse. The "single door" architecture:

```
internet → Cloudflare edge → cloudflared (outbound) → nginx 127.0.0.1:8123 → API 127.0.0.1:8124
```

> **Port Note:** nginx must listen on the exact port Cloudflare Tunnel points to. If the tunnel routes `voice.*` → `localhost:8123`, then nginx takes `:8123` and the app moves to internal `:8124`.

- **API completely hidden:** `HOST=127.0.0.1` (default) — API only listens on loopback, **not** exposed to LAN. Only nginx can reach it.
- **nginx as the door:** serves UI (`frontend/dist/`) + proxies `/v1/*` with `proxy_buffering off` (allows mp3 streaming immediately, avoiding Cloudflare 524 timeouts), `client_max_body_size 25m`, and passes `CF-Connecting-IP` to the app. The app **only trusts** this IP header when the peer is loopback (via nginx). Sample config: `deploy/nginx.conf.example`.
- **Cloudflare Tunnel (user configured):** `cloudflared` opens an outbound connection to the edge, **0 inbound ports**, 0 public IPs. Steps + sample `config.yml` + **CF dashboard checklist** (rate-rule on `/v1/audio/*`, WAF blocking scanners, Bot Fight Mode) are in: `deploy/cloudflare-tunnel.md`.

**Self-protection layer in app (enabled by `ANON_ENABLED=true`).** Independent of the edge — the edge is just an extra layer. The app gates based on **actual cost**:

- Token-bucket rate-limit by IP + **daily budget** (characters for TTS, audio seconds for ASR) stored in SQLite; refunds budget on errors. Anonymous IP exceeding limits → 429/413 **immediately**, no hanging.
- Admission control: concurrent limits + bounded queues → fails fast instead of holding requests until crash. Long text → uses `/v1/audio/stream` (reads long files, mp3 streams).
- Having a **valid API key** = TRUSTED tier (bypasses rate/budget limits). No key = anonymous tier (gated). CRUD operations on cloned voices **always require a key**; discovery (`/v1/voices`, `/v1/models`, previews) is public.

> ⚠️ **Keep `WORKERS=1` when `ANON_ENABLED=true`.** The gate runs in-memory per process + a single-writer SQLite budget; increasing workers multiplies the limit N times and causes `database is locked` errors.

**CPU limiting via systemd.** Because onnxruntime may **ignore** `OMP_NUM_THREADS`, `deploy/install-service.sh` sets `Environment=OMP_NUM_THREADS` and strictly limits **`CPUQuota=400%`** (≈4 cores). Includes crash-loop backoff.

Quick steps (after running `install-service.sh` for API):

```bash
sudo apt install nginx
(cd frontend && npm ci && npm run build)
sudo mkdir -p /var/www/all-voice && sudo cp -r frontend/dist/* /var/www/all-voice/
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/all-voice
sudo ln -sf /etc/nginx/sites-available/all-voice /etc/nginx/sites-enabled/all-voice
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
# then follow deploy/cloudflare-tunnel.md to set up Tunnel + CF checklist.
```

## macOS (No systemd)

Temporary background run: `nohup uv run uvicorn app.main:app --host 127.0.0.1 --port 8124 >> logs/server.log 2>&1 &`. For persistence, use `launchd`.

## GPU (Optional, Linux + NVIDIA)

Default is torch CPU. For CUDA: install the CUDA version of torch from PyTorch index, set `DEVICE=cuda` in `.env`, and `restart` the service. Leave macOS as `DEVICE=cpu` (ONNX).

## Porting Cloned Voices

Copy the `data/voices/` folder (samples + `registry.json`) to the new machine → the app will automatically re-enroll them at startup.

## Updates

```bash
git pull
bash deploy/setup.sh                 # sync dependencies with new lock
sudo systemctl restart all-voice
```
