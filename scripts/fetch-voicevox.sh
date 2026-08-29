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
ORT_DIR="$DEST/onnxruntime"
# Version-independent symlink -> the versioned lib the downloader delivers. The
# app's default config points here (voicevox_onnxruntime), so no env is needed.
ORT_LINK="$ORT_DIR/lib/libvoicevox_onnxruntime.so"
mkdir -p "$DEST" "$VVM_DIR"

# Resolve the Python that has the app's venv (prefer uv-managed .venv).
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || PY="python3"

# 1) Install the voicevox_core wheel (skip if already importable). A uv-managed
# venv ships no pip, so prefer `uv pip install` when uv is on PATH.
if "$PY" -c "import voicevox_core" >/dev/null 2>&1; then
  echo "skip  voicevox_core already importable"
elif command -v uv >/dev/null 2>&1; then
  echo "uv pip install $WHEEL"
  uv pip install "$REL_BASE/$WHEEL"
else
  echo "pip install $WHEEL"
  "$PY" -m pip install "$REL_BASE/$WHEEL"
fi

# 2) Fetch dict + VVM models + the ONNX Runtime lib via the official downloader.
if [[ -d "$DICT_DIR" && -d "$ORT_DIR" && -n "$(find "$VVM_DIR" -maxdepth 1 -name '*.vvm' -print -quit 2>/dev/null)" ]]; then
  echo "skip  dict + VVMs + onnxruntime already present under $DEST"
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
  # The downloader REQUIRES agreeing to the VOICEVOX model + ONNX Runtime terms.
  # Interactive by default (answer y); set VOICEVOX_AGREE_TOS=1 to accept
  # non-interactively (CI) — only do so if you accept those terms.
  echo "downloading dict + VVM models + onnxruntime (~hundreds of MB)"
  if [[ "${VOICEVOX_AGREE_TOS:-}" == "1" ]]; then
    echo "VOICEVOX_AGREE_TOS=1 -> auto-agreeing to the VOICEVOX model + ONNX Runtime terms"
    yes y | "$BIN" --output "$STAGE" --exclude c-api
  else
    echo "The downloader will ask you to AGREE to the VOICEVOX terms (answer y)."
    "$BIN" --output "$STAGE" --exclude c-api
  fi

  # Relocate to the config-default layout, wherever the downloader put them.
  found_dict="$(find "$STAGE" -type d -name 'open_jtalk_dic_utf_8*' -print -quit || true)"
  if [[ -n "$found_dict" && ! -d "$DICT_DIR" ]]; then
    mv "$found_dict" "$DICT_DIR"
  fi
  while IFS= read -r vvm; do
    mv -n "$vvm" "$VVM_DIR/"
  done < <(find "$STAGE" -type f -name '*.vvm')
  # Keep the onnxruntime lib (the wheel bundles none) and expose a stable,
  # version-independent symlink at the app's default path.
  found_ort="$(find "$STAGE" -type d -name onnxruntime -print -quit || true)"
  if [[ -n "$found_ort" && ! -d "$ORT_DIR" ]]; then
    mv "$found_ort" "$ORT_DIR"
  fi
  if [[ ! -e "$ORT_LINK" ]]; then
    versioned="$(find "$ORT_DIR/lib" -maxdepth 1 -name 'libvoicevox_onnxruntime.so.*' -print -quit 2>/dev/null || true)"
    [[ -n "$versioned" ]] && ln -sf "$(basename "$versioned")" "$ORT_LINK"
  fi
  rm -rf "$STAGE"
fi

# 3) Verify.
vvm_count="$(find "$VVM_DIR" -maxdepth 1 -name '*.vvm' | wc -l | tr -d ' ')"
if [[ ! -d "$DICT_DIR" || "$vvm_count" -eq 0 || ! -e "$ORT_LINK" ]]; then
  echo "ERROR: expected dict dir + >=1 VVM + onnxruntime lib, got" \
       "dict=$([[ -d "$DICT_DIR" ]] && echo ok || echo MISSING)" \
       "vvms=$vvm_count" \
       "onnxruntime=$([[ -e "$ORT_LINK" ]] && echo ok || echo MISSING)" >&2
  echo "Inspect $DEST and set VOICEVOX_DICT_DIR / VOICEVOX_VVM_DIR / VOICEVOX_ONNXRUNTIME to match." >&2
  exit 4
fi

echo
echo "VOICEVOX assets ready:"
echo "  dict:        $DICT_DIR"
echo "  vvms:        $VVM_DIR ($vvm_count model file(s))"
echo "  onnxruntime: $ORT_LINK"
echo "Remember the VOICEVOX credit obligation when publishing audio."
