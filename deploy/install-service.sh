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
  echo "macOS: run in the background with launchd, or: nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8123 >> logs/server.log 2>&1 &" >&2
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
HOST="$(_env_val HOST)";  HOST="${HOST:-0.0.0.0}"
PORT="$(_env_val PORT)";  PORT="${PORT:-8123}"
WORKERS="${WORKERS:-2}"

mkdir -p "$APP_DIR/logs"
chown -R "$RUN_USER" "$APP_DIR/logs" 2>/dev/null || true

UNIT=/etc/systemd/system/all-voice.service
echo "==> Writing $UNIT  (user=$RUN_USER, bind=$HOST:$PORT, workers=$WORKERS)"
cat > "$UNIT" <<EOF
[Unit]
Description=all-voice TTS gateway
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP_DIR
ExecStart=$UV run uvicorn app.main:app --host $HOST --port $PORT --workers $WORKERS
Restart=always
RestartSec=3
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
