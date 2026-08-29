"""Round-trip: TTS output fed back into ASR ("sub").

Proves the synthesized voice is intelligible (stronger than an RMS floor) and
exercises the transcriptions feature end to end. `ASR_MODEL=tiny` is set BEFORE
the app imports/caches settings (same pattern as tests/test_transcriptions.py) so
the round-trip never pulls the heavier default model.

Skips cleanly when the TTS engine's assets or the `asr` extra are absent.
"""

from __future__ import annotations

import os
import re

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
os.environ["ASR_MODEL"] = "tiny"  # keep the round-trip fast

from app.config import get_settings  # noqa: E402

# Force a re-read so ASR_MODEL=tiny wins even if another module imported the app
# (and cached settings) earlier in the session.
get_settings.cache_clear()

from app import asr  # noqa: E402
from app.backends.kokoro_backend import KokoroBackend  # noqa: E402
from app.backends.voicevox_backend import VoicevoxBackend  # noqa: E402
from app.main import app  # noqa: E402

SETTINGS = get_settings()
client = TestClient(app)
AUTH = {"Authorization": "Bearer test-key"}

ASR_READY = asr.is_available()


def _speak(model: str, voice: str, text: str) -> bytes:
    r = client.post(
        "/v1/audio/speech", headers=AUTH,
        json={"model": model, "voice": voice, "input": text, "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    return r.content


def _transcribe(wav: bytes) -> dict:
    r = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("speech.wav", wav, "audio/wav")},
        data={"response_format": "verbose_json"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _tokens(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


@pytest.mark.synth
@pytest.mark.skipif(not ASR_READY, reason="asr extra not installed")
@pytest.mark.skipif(
    not KokoroBackend.is_available(SETTINGS), reason="kokoro assets not installed"
)
def test_kokoro_roundtrip_english():
    text = "the quick brown fox jumps over the lazy dog"
    result = _transcribe(_speak("kokoro", "af_heart", text))
    assert result["text"].strip(), "empty transcription"
    assert result["duration"] > 0

    want = _tokens(text)
    got = _tokens(result["text"])
    hit = len(want & got) / len(want)
    assert hit >= 0.6, f"only {hit:.0%} of input words recognised: {result['text']!r}"


@pytest.mark.synth
@pytest.mark.skipif(not ASR_READY, reason="asr extra not installed")
@pytest.mark.skipif(
    not VoicevoxBackend.is_available(SETTINGS), reason="voicevox assets not installed"
)
def test_voicevox_roundtrip_japanese():
    # Loose: whisper `tiny` transcribes Japanese poorly, so only assert the round
    # trip produced non-empty text with real duration (content is logged, not gated).
    voices = client.get("/v1/voices?language=ja", headers=AUTH).json()["data"]
    assert voices, "no Japanese voices"
    result = _transcribe(_speak("voicevox", voices[0]["id"], "こんにちは、世界。"))
    print(f"\n[voicevox->asr] {result['text']!r}")
    assert result["text"].strip(), "empty transcription"
    assert result["duration"] > 0
