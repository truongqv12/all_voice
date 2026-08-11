"""End-to-end API test: boots the app in-process (real VieNeu backend) and
exercises every endpoint, including a real synthesis for each audio format."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
AUTH = {"Authorization": "Bearer test-key"}

from app.main import app  # noqa: E402  (import after env is set)

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_required():
    assert client.get("/v1/models").status_code == 401
    assert client.get("/v1/voices").status_code == 401
    r = client.post("/v1/audio/speech", json={"model": "vieneu", "input": "hi", "voice": "x"})
    assert r.status_code == 401
    assert "error" in r.json()


def test_models():
    r = client.get("/v1/models", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    assert "vieneu" in [m["id"] for m in body["data"]]


def test_voices():
    r = client.get("/v1/voices", headers=AUTH)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) > 0
    assert {"id", "name", "model"} <= data[0].keys()


def test_validation_error():
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "x" * 5000, "voice": "Trúc Ly"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request_error"


@pytest.mark.parametrize(
    "fmt,ctype",
    [
        ("wav", "audio/wav"),
        ("pcm", "audio/pcm"),
        ("mp3", "audio/mpeg"),
        ("flac", "audio/flac"),
        ("opus", "audio/ogg"),
        ("aac", "audio/aac"),
    ],
)
def test_speech_formats(fmt, ctype):
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "Xin chào.", "voice": "Trúc Ly", "response_format": fmt},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == ctype
    assert len(r.content) > 0


def test_openai_alias():
    # Unknown OpenAI model + voice must fall back, not error.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "tts-1", "input": "Xin chào.", "voice": "alloy", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


def _wav_seconds(b: bytes) -> float:
    return max(len(b) - 44, 0) / 2 / 48000  # 16-bit mono 48kHz


def test_speed_changes_duration():
    text = "Đây là câu kiểm tra tốc độ đọc của hệ thống."
    def synth(speed):
        r = client.post("/v1/audio/speech", headers=AUTH,
                        json={"model": "vieneu", "input": text, "voice": "Trúc Ly",
                              "response_format": "wav", "speed": speed})
        assert r.status_code == 200, r.text
        return _wav_seconds(r.content)
    base, fast = synth(1.0), synth(2.0)
    assert fast < base * 0.7  # ~2x faster -> markedly shorter


def test_tuning_options():
    # Valid knobs (VieNeu style + pause scale + sampling) are accepted.
    ok = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={
            "model": "vieneu", "input": "Kể chuyện nhé.", "voice": "Trúc Ly",
            "response_format": "wav", "style": "doc_truyen",
            "silence_p": 0.3, "temperature": 0.6, "max_chars": 200,
        },
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.content) > 0

    # Out-of-range / invalid knobs are rejected with 400.
    bad = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "x", "voice": "Trúc Ly", "style": "opera"},
    )
    assert bad.status_code == 400


def test_voice_clone_lifecycle():
    # Real reference clip (a few seconds of Vietnamese speech).
    sample = (Path(__file__).parent / "clone_1.wav").read_bytes()
    assert len(sample) > 0

    # Enrol (OpenAI multipart shape: name + audio_sample; consent optional here).
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("sample.wav", sample, "audio/wav")},
        data={"name": "My Clone"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["object"] == "audio.voice" and body["id"].startswith("voice_")
    voice_id = body["id"]

    # It appears in both the OpenAI list and the merged /v1/voices.
    listed = client.get("/v1/audio/voices", headers=AUTH).json()["data"]
    assert voice_id in [v["id"] for v in listed]
    assert voice_id in [v["id"] for v in client.get("/v1/voices", headers=AUTH).json()["data"]]

    # Synthesize with the clone via the OpenAI voice-object form {"id": ...}.
    spoken = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "Xin chào từ giọng nhân bản.", "voice": {"id": voice_id}, "response_format": "wav"},
    )
    assert spoken.status_code == 200, spoken.text
    assert len(spoken.content) > 0

    # Delete.
    deleted = client.delete(f"/v1/audio/voices/{voice_id}", headers=AUTH)
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert client.get(f"/v1/audio/voices/{voice_id}", headers=AUTH).status_code == 404


def test_voice_consent_stub():
    r = client.post(
        "/v1/audio/voice_consents",
        headers=AUTH,
        files={"recording": ("c.wav", b"RIFFxxxx", "audio/wav")},
        data={"language": "vi-VN", "name": "consent"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"].startswith("cons_")
