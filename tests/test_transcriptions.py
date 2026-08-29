"""Transcriptions endpoint + subtitle formatter tests.

Formatter/auth/validation/503 tests are pure and fast (no model). The e2e tests
load a real `tiny` faster-whisper model once and transcribe `clone_1.wav`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
os.environ["ASR_MODEL"] = "tiny"  # small model keeps the e2e tests fast

from app.config import get_settings  # noqa: E402  (import after env is set)

# Force a re-read so ASR_MODEL=tiny wins even if another test module already
# imported the app (and cached settings) earlier in the session.
get_settings.cache_clear()

from app.asr import (  # noqa: E402
    AsrUnavailableError,
    Segment,
    TranscriptionResult,
    Word,
    format_timestamp,
    to_srt,
    to_verbose_json,
    to_vtt,
)
from app.main import app  # noqa: E402

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-key"}
CLONE = Path(__file__).parent / "clone_1.wav"


def _seg(seg_id: int, start: float, end: float, text: str) -> Segment:
    return Segment(
        id=seg_id, seek=0, start=start, end=end, text=text,
        temperature=0.0, avg_logprob=-0.3, compression_ratio=1.1, no_speech_prob=0.01,
        tokens=[50364, 123],
    )


# --- Unit: formatters (no model) ---

def test_format_timestamp_srt_vs_vtt():
    assert format_timestamp(0.0, sep=",") == "00:00:00,000"
    assert format_timestamp(1.5, sep=",") == "00:00:01,500"
    assert format_timestamp(3661.25, sep=".") == "01:01:01.250"


def test_to_srt():
    srt = to_srt([_seg(0, 0.0, 1.5, " Xin chào."), _seg(1, 1.5, 3.25, " Tạm biệt.")])
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,500\nXin chào.")
    assert "2\n00:00:01,500 --> 00:00:03,250\nTạm biệt." in srt


def test_to_vtt():
    vtt = to_vtt([_seg(0, 0.0, 1.5, " Hello")])
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.500" in vtt


def test_to_verbose_json_words_optional():
    segs = [_seg(0, 0.0, 1.0, "hi")]
    without = to_verbose_json(TranscriptionResult("hi", "vi", 1.0, segs))
    assert without["task"] == "transcribe" and "words" not in without
    assert without["segments"][0]["no_speech_prob"] == 0.01
    assert without["segments"][0]["tokens"] == [50364, 123]  # OpenAI segment field
    with_words = to_verbose_json(
        TranscriptionResult("hi", "vi", 1.0, segs, [Word("hi", 0.0, 0.4, 0.9)])
    )
    assert with_words["words"] == [{"word": "hi", "start": 0.0, "end": 0.4}]


# --- 503 / auth / validation (no model) ---

def test_asr_unavailable_returns_503(monkeypatch):
    def _boom(*_a, **_k):
        raise AsrUnavailableError("nope")

    monkeypatch.setattr("app.routers.transcriptions.transcribe", _boom)
    r = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("a.wav", b"RIFFxxxx", "audio/wav")},
    )
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "asr_unavailable"


def test_transcriptions_auth_required():
    r = client.post(
        "/v1/audio/transcriptions", files={"file": ("a.wav", b"x", "audio/wav")}
    )
    assert r.status_code == 401


def test_empty_file_400():
    r = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("a.wav", b"", "audio/wav")},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_audio_file"


def test_undecodable_file_returns_400():
    # Non-empty but not real audio -> faster-whisper's av decode fails; the router
    # must return a clean 400 (OpenAI contract), not a 500.
    r = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("notes.txt", b"this is plain text, not audio " * 8, "text/plain")},
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "invalid_audio_file"


# --- E2E: real tiny model on clone_1.wav ---

@pytest.fixture(scope="module")
def audio_bytes() -> bytes:
    return CLONE.read_bytes()


def test_e2e_verbose_json(audio_bytes):
    r = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("clone_1.wav", audio_bytes, "audio/wav")},
        data={"response_format": "verbose_json"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["task"] == "transcribe" and j["text"].strip()
    assert j["duration"] > 0
    assert j["segments"] and j["segments"][0]["start"] < j["segments"][0]["end"]
    assert isinstance(j["segments"][0]["tokens"], list)  # OpenAI segment field


def test_e2e_srt_and_vtt(audio_bytes):
    srt = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("clone_1.wav", audio_bytes, "audio/wav")},
        data={"response_format": "srt"},
    )
    assert srt.status_code == 200 and "-->" in srt.text
    assert srt.headers["content-type"].startswith("text/plain")

    vtt = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("clone_1.wav", audio_bytes, "audio/wav")},
        data={"response_format": "vtt"},
    )
    assert vtt.status_code == 200 and vtt.text.startswith("WEBVTT")


def test_e2e_word_timestamps(audio_bytes):
    r = client.post(
        "/v1/audio/transcriptions", headers=AUTH,
        files={"file": ("clone_1.wav", audio_bytes, "audio/wav")},
        data={"response_format": "verbose_json", "timestamp_granularities[]": "word"},
    )
    assert r.status_code == 200, r.text
    words = r.json()["words"]
    assert words and all(w["start"] <= w["end"] for w in words)
