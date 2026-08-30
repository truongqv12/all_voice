#!/usr/bin/env bash
# Install all-voice as a systemd service (Linux only) so it runs in the
# background, survives reboots, and auto-restarts on crash — no terminal held.
# The unit file is generated from the real project path, user, and .env PORT.
#
# Usage:
#   sudo bash deploy/install-service.sh
#   WORKERS=4 sudo bash deploy/install-service.sh   # override worker count
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  echo "systemd is Linux-only." >&2
  echo "macOS: run in the background with launchd, or: nohup uv run uvicorn app.main:app --host 127.0.0.1 --port 8124 >> logs/server.log 2>&1 &" >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash deploy/install-service.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Run the service as the human who invoked sudo, not root (uv lives in their HOME).
RUN_USER="${SUDO_USER:-root}"

# Resolve uv: usually in the invoking user's ~/.local/bin, absent from root's PATH.
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  UV="$(sudo -u "$RUN_USER" bash -lc 'command -v uv' 2>/dev/null || true)"
fi
[ -n "$UV" ] || { echo "uv not found — run 'bash deploy/setup.sh' first." >&2; exit 1; }

# Pull HOST/PORT from .env, fall back to safe defaults.
_env_val() { grep -E "^$1=" "$APP_DIR/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '[:space:]'; }
# Default HOST is loopback: the API must stay hidden behind nginx + Cloudflare
# Tunnel, never reachable from the LAN. Set HOST=0.0.0.0 in .env only for a
# trusted private box. See docs/deployment.md.
HOST="$(_env_val HOST)";  HOST="${HOST:-127.0.0.1}"
PORT="$(_env_val PORT)";  PORT="${PORT:-8124}"
ANON_ENABLED="$(_env_val ANON_ENABLED)"
# 1 worker by default: each worker loads its own TTS + ASR model into RAM, and
# inference is CPU-bound (CTranslate2/torch saturate all cores) so extra workers
# raise memory without adding throughput on this box. Override with WORKERS=N.
WORKERS="${WORKERS:-1}"
# Thread + CPU ceiling for the CPU-bound synth/ASR work. OMP_NUM_THREADS caps the
# OpenMP pools; CPU_QUOTA is a hard cgroup cap so one runaway request can never eat
# all 6 cores and starve the box (onnxruntime may ignore the thread env — the
# cgroup cap is the real backstop). 400% = 4 cores' worth, leaving headroom for
# nginx + the OS. To pin to specific cores instead, set CPU_ALLOWED (e.g. "0-3").
OMP_THREADS="${OMP_THREADS:-4}"
CPU_QUOTA="${CPU_QUOTA:-400%}"
CPU_ALLOWED="${CPU_ALLOWED:-}"

# The anon gate (rate/budget/admission) is per-process in-memory + a single-writer
# SQLite budget; it only holds with ONE worker. Refuse a footgun combo loudly.
if [ "${ANON_ENABLED,,}" = "true" ] && [ "$WORKERS" -gt 1 ]; then
  echo "ERROR: ANON_ENABLED=true needs WORKERS=1 — extra workers multiply every" >&2
  echo "       per-IP limit by N and cause 'database is locked'. The app itself" >&2
  echo "       refuses to start in this combo. Set WORKERS=1 or ANON_ENABLED=false." >&2
  exit 1
fi

mkdir -p "$APP_DIR/logs"
chown -R "$RUN_USER" "$APP_DIR/logs" 2>/dev/null || true

# Pick the CPU cap directive: AllowedCPUs (core pinning) if CPU_ALLOWED is set,
# else the portable CPUQuota. Both are cgroup-enforced by systemd.
if [ -n "$CPU_ALLOWED" ]; then
  CPU_CAP="AllowedCPUs=$CPU_ALLOWED"
else
  CPU_CAP="CPUQuota=$CPU_QUOTA"
fi

UNIT=/etc/systemd/system/all-voice.service
echo "==> Writing $UNIT  (user=$RUN_USER, bind=$HOST:$PORT, workers=$WORKERS, $CPU_CAP)"
cat > "$UNIT" <<EOF
[Unit]
Description=all-voice TTS gateway
After=network.target
# Crash-loop backoff: if it dies >5 times in 60s, stop retrying (a wedged model or
# bad config shouldn't hammer this small box). Clear with: systemctl reset-failed.
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP_DIR
# Cap the OpenMP thread pools before the model loads (belt; the cgroup cap below is
# the braces since onnxruntime may ignore this).
Environment=OMP_NUM_THREADS=$OMP_THREADS
Environment=INFERENCE_THREADS=$OMP_THREADS
# Cap glibc malloc arenas. Under a concurrency spike the anyio threadpool spawns many
# threads; glibc gives each its own arena and never returns that memory to the OS, so
# RSS balloons to a high-water mark (seen ~7GB after a 40-request burst) and stays there.
# Synthesis is serialized (max_concurrency=1) so 2 arenas are plenty — this keeps the
# burst peak bounded on this 11GB box.
Environment=MALLOC_ARENA_MAX=2
ExecStart=$UV run uvicorn app.main:app --host $HOST --port $PORT --workers $WORKERS
Restart=always
RestartSec=3
# Hard CPU ceiling so one runaway synthesis can't pin all cores and hang the box.
$CPU_CAP
# Capture uvicorn + native-crash output (stderr) that the app's app.log can't.
StandardOutput=append:$APP_DIR/logs/server.log
StandardError=append:$APP_DIR/logs/server.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now all-voice

echo "==> Service is up."
echo "    Status : systemctl status all-voice"
echo "    Live   : journalctl -u all-voice -f   (or: tail -f $APP_DIR/logs/server.log)"
echo "    Restart: sudo systemctl restart all-voice"
echo "    Stop   : sudo systemctl disable --now all-voice"
