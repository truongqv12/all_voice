"""Kokoro (English) backend tests.

Fast unit tests (no marker) exercise the table-driven voice list + resolution
without any model. The `synth` tests need the downloaded model (bash
scripts/fetch-kokoro.sh) and `espeak-ng`; they skip cleanly when absent.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
AUTH = {"Authorization": "Bearer test-key"}

from conftest import assert_real_audio, save_wav  # noqa: E402
from app.backends.kokoro_backend import KokoroBackend  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402  (import after env is set)

SETTINGS = get_settings()
client = TestClient(app)

requires_kokoro = pytest.mark.skipif(
    not KokoroBackend.is_available(SETTINGS), reason="kokoro assets not installed"
)


# --- Unit (no model) ---

def test_kokoro_lists_28_english_voices():
    voices = KokoroBackend(SETTINGS).list_voices()
    assert len(voices) == 28
    assert len({v.id for v in voices}) == 28
    assert all(v.language == "en" and v.model == "kokoro" for v in voices)
    assert sum(v.id.startswith("a") for v in voices) == 20  # US
    assert sum(v.id.startswith("b") for v in voices) == 8  # UK


def test_kokoro_is_available_false_without_files(tmp_path):
    class S:
        kokoro_model_path = str(tmp_path / "missing.onnx")
        kokoro_voices_path = str(tmp_path / "missing.bin")

    assert KokoroBackend.is_available(S) is False


def test_kokoro_resolve_voice_strict_and_lenient():
    kb = KokoroBackend(SETTINGS)
    assert kb.resolve_voice("af_heart", strict=True) == "af_heart"
    assert kb.resolve_voice("Heart (US, nữ)", strict=True) == "af_heart"  # by name
    assert kb.resolve_voice("does-not-exist", strict=True) is None
    assert kb.resolve_voice("alloy", strict=False) == SETTINGS.kokoro_default_voice


# --- Synth (needs model + espeak-ng) ---

@pytest.mark.synth
@requires_kokoro
def test_kokoro_synthesizes_multiple_voices():
    kb = KokoroBackend(SETTINGS)
    text = "The quick brown fox jumps over the lazy dog."
    rendered = {}
    for vid in ("af_heart", "am_adam", "bf_emma"):  # US female, US male, UK female
        res = kb.synthesize(text, vid)
        assert_real_audio(res.pcm, res.sample_rate)
        save_wav(res.pcm, res.sample_rate, f"kokoro-{vid}.wav")
        rendered[vid] = res.pcm
    assert not np.array_equal(rendered["af_heart"], rendered["am_adam"])


@pytest.mark.synth
@requires_kokoro
def test_kokoro_http_speech():
    ok = client.post(
        "/v1/audio/speech", headers=AUTH,
        json={"model": "kokoro", "voice": "af_heart", "input": "Hello world.", "response_format": "mp3"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.headers["content-type"] == "audio/mpeg"
    assert len(ok.content) > 2000

    bad = client.post(
        "/v1/audio/speech", headers=AUTH,
        json={"model": "kokoro", "voice": "nope", "input": "x"},
    )
    assert bad.status_code == 404
    assert bad.json()["error"]["code"] == "unknown_voice"


@pytest.mark.synth
@requires_kokoro
def test_kokoro_duration_scales_with_speed():
    kb = KokoroBackend(SETTINGS)
    text = "The quick brown fox jumps over the lazy dog."
    slow = kb.synthesize(text, "af_heart", speed=1.0)
    fast = kb.synthesize(text, "af_heart", speed=1.4)
    assert len(fast.pcm) < 0.9 * len(slow.pcm)  # faster => shorter audio
