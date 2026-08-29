#!/usr/bin/env bash
# Download the Kokoro-82M v1.0 ONNX model + voices for the English backend.
#
# Torch-free: this only fetches two files (an ONNX graph + a voices blob) into
# models/kokoro/. The runtime is provided by the `en` extra (`uv sync --extra en`)
# and English G2P needs the system package `espeak-ng` (`apt-get install espeak-ng`).
#
# Usage:
#   bash scripts/fetch-kokoro.sh            # int8 (88 MB, default, lightest)
#   KOKORO_PRECISION=fp16 bash scripts/fetch-kokoro.sh   # fp16 (169 MB)
#
# Idempotent: an already-present file of plausible size is left untouched.
set -euo pipefail

PRECISION="${KOKORO_PRECISION:-int8}"
case "$PRECISION" in
  int8) MODEL_FILE="kokoro-v1.0.int8.onnx"; MIN_BYTES=$((60 * 1024 * 1024)) ;;
  fp16) MODEL_FILE="kokoro-v1.0.fp16.onnx"; MIN_BYTES=$((140 * 1024 * 1024)) ;;
  *) echo "KOKORO_PRECISION must be int8 or fp16 (got '$PRECISION')" >&2; exit 2 ;;
esac

BASE_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
VOICES_FILE="voices-v1.0.bin"
VOICES_MIN_BYTES=$((1 * 1024 * 1024))

DEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/models/kokoro"
mkdir -p "$DEST_DIR"

# fetch <url> <path> <min_bytes>: download unless a file >= min_bytes already exists.
fetch() {
  local url="$1" path="$2" min_bytes="$3"
  if [[ -f "$path" ]]; then
    local size
    size=$(stat -c%s "$path" 2>/dev/null || stat -f%z "$path")
    if (( size >= min_bytes )); then
      echo "skip  $path ($((size / 1024 / 1024)) MB already present)"
      return 0
    fi
    echo "re-download $path (size ${size}B < ${min_bytes}B, looks incomplete)"
  fi
  echo "fetch $url"
  echo "   -> $path"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 -o "$path" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$path" "$url"
  else
    echo "need curl or wget on PATH" >&2; exit 3
  fi
}

fetch "$BASE_URL/$MODEL_FILE" "$DEST_DIR/$MODEL_FILE" "$MIN_BYTES"
fetch "$BASE_URL/$VOICES_FILE" "$DEST_DIR/$VOICES_FILE" "$VOICES_MIN_BYTES"

echo
echo "Kokoro assets ready in $DEST_DIR"
echo "  model:  $MODEL_FILE"
echo "  voices: $VOICES_FILE"
if [[ "$PRECISION" != "int8" ]]; then
  echo "Note: set KOKORO_MODEL_PATH=models/kokoro/$MODEL_FILE so the app uses this precision."
fi
