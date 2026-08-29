#!/usr/bin/env bash
# Install VOICEVOX Core (Japanese backend) + its OpenJTalk dict and VVM voice
# models. In-process runtime: the `voicevox_core` wheel is NOT on PyPI, so it is
# installed from a pinned GitHub release; the dict + VVM assets are pulled by
# VOICEVOX's own `download` binary. All output is arranged to match the app's
# default config paths (models/voicevox/open_jtalk_dic_utf_8-1.11 and
# models/voicevox/vvms).
#
# CREDIT: VOICEVOX voices require crediting the character when you publish audio
# (e.g. "VOICEVOX:ずんだもん"). The backend surfaces this on GET /v1/voices.
#
# Usage:
#   bash scripts/fetch-voicevox.sh
#   VOICEVOX_CORE_VERSION=0.17.0 bash scripts/fetch-voicevox.sh   # pin a version
#
# Pin the wheel and the assets to the SAME release to avoid version mismatch.
# Idempotent: existing dict + VVMs are left in place.
set -euo pipefail

VERSION="${VOICEVOX_CORE_VERSION:-0.17.0}"
# abi3 wheel: one cp310 build runs on 3.10–3.12. Adjust the tag on the releases
# page if your platform differs (e.g. aarch64 / macOS).
WHEEL="voicevox_core-${VERSION}-cp310-abi3-manylinux_2_34_x86_64.whl"
DOWNLOADER="download-linux-x64"
REL_BASE="https://github.com/VOICEVOX/voicevox_core/releases/download/${VERSION}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/models/voicevox"
DICT_DIR="$DEST/open_jtalk_dic_utf_8-1.11"
VVM_DIR="$DEST/vvms"
mkdir -p "$DEST" "$VVM_DIR"

# Resolve the Python that has the app's venv (prefer uv-managed .venv).
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || PY="python3"

# 1) Install the voicevox_core wheel (skip if already importable).
if "$PY" -c "import voicevox_core" >/dev/null 2>&1; then
  echo "skip  voicevox_core already importable"
else
  echo "pip install $WHEEL"
  "$PY" -m pip install "$REL_BASE/$WHEEL"
fi

# 2) Fetch dict + VVM models via the official downloader (handles onnxruntime too).
if [[ -d "$DICT_DIR" && -n "$(find "$VVM_DIR" -maxdepth 1 -name '*.vvm' -print -quit 2>/dev/null)" ]]; then
  echo "skip  dict + VVMs already present under $DEST"
else
  STAGE="$DEST/_download"
  mkdir -p "$STAGE"
  BIN="$STAGE/download"
  if [[ ! -x "$BIN" ]]; then
    echo "fetch $DOWNLOADER"
    if command -v curl >/dev/null 2>&1; then
      curl -fL --retry 3 -o "$BIN" "$REL_BASE/$DOWNLOADER"
    else
      wget -O "$BIN" "$REL_BASE/$DOWNLOADER"
    fi
    chmod +x "$BIN"
  fi
  echo "downloading dict + VVM models (this fetches ~hundreds of MB)"
  "$BIN" --output "$STAGE" --exclude c-api

  # Relocate to the config-default layout, wherever the downloader put them.
  found_dict="$(find "$STAGE" -type d -name 'open_jtalk_dic_utf_8*' -print -quit || true)"
  if [[ -n "$found_dict" && ! -d "$DICT_DIR" ]]; then
    mv "$found_dict" "$DICT_DIR"
  fi
  while IFS= read -r vvm; do
    mv -n "$vvm" "$VVM_DIR/"
  done < <(find "$STAGE" -type f -name '*.vvm')
  rm -rf "$STAGE"
fi

# 3) Verify.
vvm_count="$(find "$VVM_DIR" -maxdepth 1 -name '*.vvm' | wc -l | tr -d ' ')"
if [[ ! -d "$DICT_DIR" || "$vvm_count" -eq 0 ]]; then
  echo "ERROR: expected dict dir + >=1 VVM, got dict=$([[ -d "$DICT_DIR" ]] && echo ok || echo MISSING) vvms=$vvm_count" >&2
  echo "Inspect $DEST and set VOICEVOX_DICT_DIR / VOICEVOX_VVM_DIR to match." >&2
  exit 4
fi

echo
echo "VOICEVOX assets ready:"
echo "  dict: $DICT_DIR"
echo "  vvms: $VVM_DIR ($vvm_count model file(s))"
echo "Remember the VOICEVOX credit obligation when publishing audio."
