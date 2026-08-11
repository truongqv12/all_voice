#!/usr/bin/env bash
# all-voice — one-shot setup for a fresh Linux/macOS machine.
# Installs uv, builds the venv from the lockfile, prepares .env and logs/.
# Idempotent: safe to re-run.
#
# Usage:
#   bash deploy/setup.sh            # full install (includes PyTorch for cloning)
#   CLONE=0 bash deploy/setup.sh    # skip PyTorch (no voice cloning, lighter)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_DIR"

CLONE="${CLONE:-1}"   # 1 = install the `clone` extra (voice cloning). 0 = skip.

echo "==> all-voice setup in: $APP_DIR"

# 1. Ensure uv is installed (it also fetches the pinned Python 3.12).
if ! command -v uv >/dev/null 2>&1; then
  echo "==> Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
UV="$(command -v uv)"
echo "==> uv: $UV ($("$UV" --version))"

# 2. Install dependencies exactly as locked (uv.lock). --frozen = no silent upgrades.
if [ "$CLONE" = "1" ]; then
  echo "==> uv sync --frozen --extra clone  (includes PyTorch — voice cloning)"
  "$UV" sync --frozen --extra clone
else
  echo "==> uv sync --frozen  (no voice cloning)"
  "$UV" sync --frozen
fi

# 3. Prepare .env — never overwrite an existing one.
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from .env.example."
  echo "    !! EDIT .env: set a real API_KEYS (do not ship dev-key)."
else
  echo "==> .env already exists — left untouched."
fi

# 4. Logs directory (rotating app.log + optional server.log live here).
mkdir -p logs

echo ""
echo "==> Setup done."
echo "    Test run (foreground):"
echo "      \"$UV\" run uvicorn app.main:app --host 0.0.0.0 --port 8123"
echo "    Run as a background service (Linux, no terminal needed):"
echo "      sudo bash deploy/install-service.sh"
echo ""
echo "    Note: the VieNeu model (~313MB) downloads on the first synthesis request."
