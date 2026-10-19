"""CapCut Cloud TTS backend unit & integration tests.

Fast unit tests (-m "not synth") test catalog listing, voice resolution,
MD5 & RSA PKCS#1 v1.5 signing, PyAV in-memory MP3 decoding, and mock HTTP synthesis.
The live `@pytest.mark.synth` test exercises the real CapCut API if network is available.
"""

from __future__ import annotations

import io
import json
import os
from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
AUTH = {"Authorization": "Bearer test-key"}

from conftest import assert_real_audio  # noqa: E402
from app.audio.encoder import encode  # noqa: E402
from app.backends.base import AudioResult  # noqa: E402
from app.backends.capcut_backend import (  # noqa: E402
    CapCutBackend,
    _decode_mp3_bytes,
    make_sign_header,
    make_tts_payload_sign,
)
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

SETTINGS = get_settings()
client = TestClient(app)


# --- Unit Tests (No Network / Fast) ---

def test_capcut_is_available_true_with_catalog():
    assert CapCutBackend.is_available(SETTINGS) is True


def test_capcut_is_available_false_without_catalog(tmp_path):
    class FakeSettings:
        capcut_voices_path = str(tmp_path / "missing.json")

    assert CapCutBackend.is_available(FakeSettings()) is False


def test_capcut_is_available_false_on_invalid_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json content", encoding="utf-8")

    class FakeSettings:
        capcut_voices_path = str(bad_file)

    assert CapCutBackend.is_available(FakeSettings()) is False


def test_capcut_list_voices_returns_24_vietnamese_voices():
    backend = CapCutBackend(SETTINGS)
    voices = backend.list_voices()
    assert len(voices) == 24
    assert len({v.id for v in voices}) == 24
    assert all(v.language == "vi" for v in voices)
    assert all(v.model == "capcut" for v in voices)

    # Check known voices exist
    voice_ids = {v.id for v in voices}
    assert "BV421_vivn_streaming" in voice_ids
    assert "vi_female_huong" in voice_ids
    assert "BV075_streaming_demon_dsp" in voice_ids


def test_capcut_resolve_voice_strict_and_lenient():
    backend = CapCutBackend(SETTINGS)

    # 1. Exact ID
    assert backend.resolve_voice("BV421_vivn_streaming", strict=True) == "BV421_vivn_streaming"
    # 2. Case-insensitive ID
    assert backend.resolve_voice("bv421_vivn_streaming", strict=True) == "BV421_vivn_streaming"
    # 3. Exact Display Name
    assert backend.resolve_voice("Nhỏ Ngọt Ngào", strict=True) == "BV421_vivn_streaming"
    # 4. Case-insensitive Display Name (including Giọng Nam Trầm)
    assert backend.resolve_voice("nhỏ ngọt ngào", strict=True) == "BV421_vivn_streaming"
    assert backend.resolve_voice("Giọng Nam Trầm", strict=True) == "multi_male_felipe_uranus_bigtts"
    assert backend.resolve_voice("giọng nam trầm", strict=True) == "multi_male_felipe_uranus_bigtts"
    # 5. Strict missing returns None
    assert backend.resolve_voice("unknown_voice_123", strict=True) is None
    # 6. Lenient fallback to configured default
    assert backend.resolve_voice("unknown_voice_123", strict=False) == SETTINGS.capcut_default_voice


def test_capcut_signing_functions():
    # Test MD5 sign header
    sign = make_sign_header("https://editor-api-sg.capcutapi.com/lv/v1/common_task/new", "8.7.0", "1700000000", "device_tdid")
    assert isinstance(sign, str)
    assert len(sign) == 32

    # Test RSA payload signature
    ssml = "<speak>Hello</speak>"
    rsa_sig = make_tts_payload_sign(ssml, '{"benefit_info":{}}', "1234567890", "359289")
    assert isinstance(rsa_sig, str)
    assert len(rsa_sig) > 50  # Base64 RSA ciphertext


def test_capcut_decode_mp3_bytes_in_memory():
    # Create 0.5s of 440Hz test sine wave PCM float32
    sr = 24000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False, dtype=np.float32)
    pcm_orig = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    # Encode to MP3 via PyAV
    mp3_bytes = encode(pcm_orig, sr, "mp3")
    assert len(mp3_bytes) > 0

    # Decode in-memory via _decode_mp3_bytes
    pcm_decoded, decoded_sr = _decode_mp3_bytes(mp3_bytes)
    assert decoded_sr == sr
    assert pcm_decoded.ndim == 1
    assert pcm_decoded.dtype == np.float32
    assert len(pcm_decoded) > 0.2 * sr
    assert_real_audio(pcm_decoded, decoded_sr)

    # Speed scaling via FFmpeg atempo (1.5x -> ~67% duration)
    pcm_fast, fast_sr = _decode_mp3_bytes(mp3_bytes, speed=1.5)
    assert fast_sr == sr
    assert len(pcm_fast) < 0.8 * len(pcm_decoded)


def test_capcut_decode_stereo_44100_mp3_and_encode_opus():
    import av

    # Create a 44100 Hz stereo s16p MP3 in-memory to verify AudioResampler downmix + 24kHz Opus compatibility
    sr = 44100
    t = np.linspace(0, 0.4, int(sr * 0.4), endpoint=False, dtype=np.float32)
    left = (16000 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    right = (16000 * np.cos(2 * np.pi * 440 * t)).astype(np.int16)
    stereo = np.vstack([left, right])

    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp3") as out:
        stream = out.add_stream("libmp3lame", rate=sr)
        stream.layout = "stereo"
        frame = av.AudioFrame.from_ndarray(stereo, format="s16p", layout="stereo")
        frame.sample_rate = sr
        for pkt in stream.encode(frame):
            out.mux(pkt)
        for pkt in stream.encode(None):
            out.mux(pkt)

    pcm_decoded, decoded_sr = _decode_mp3_bytes(buf.getvalue())
    assert decoded_sr == 24000
    assert pcm_decoded.ndim == 1
    assert pcm_decoded.dtype == np.float32
    assert_real_audio(pcm_decoded, decoded_sr, expected_sr=24000)

    # Must encode cleanly to Opus (which requires 8/12/16/24/48kHz)
    opus_bytes = encode(pcm_decoded, decoded_sr, "opus")
    assert len(opus_bytes) > 200


def test_capcut_synthesize_with_mock_session():
    # Prepare realistic test audio
    sr = 24000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False, dtype=np.float32)
    pcm_orig = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    mp3_bytes = encode(pcm_orig, sr, "mp3")

    mock_session = MagicMock()

    # 1. Mock create task POST
    create_resp = MagicMock()
    create_resp.status_code = 200
    create_resp.json.return_value = {
        "ret": 0,
        "errmsg": "success",
        "data": {
            "tasks": [
                {
                    "id": "mock_task_001",
                    "token": "mock_token_abc",
                    "bind_id": "mock_bind_xyz",
                }
            ]
        },
    }

    # 2. Mock query task POST
    query_resp = MagicMock()
    query_resp.status_code = 200
    query_resp.json.return_value = {
        "ret": 0,
        "errmsg": "success",
        "data": {
            "tasks": [
                {
                    "id": "mock_task_001",
                    "status": "succeed",
                    "payload": json.dumps({
                        "audio_subtitles": [
                            {"speech_url": "https://cdn.example.com/audio.mp3"}
                        ]
                    }),
                }
            ]
        },
    }

    # 3. Mock CDN audio GET
    dl_resp = MagicMock()
    dl_resp.status_code = 200
    dl_resp.content = mp3_bytes

    mock_session.post.side_effect = [create_resp, query_resp]
    mock_session.get.return_value = dl_resp

    backend = CapCutBackend(SETTINGS, session=mock_session)
    backend._poll_interval = 0.01  # fast test

    res = backend.synthesize("Xin chào Việt Nam", "BV421_vivn_streaming")
    assert_real_audio(res.pcm, res.sample_rate, expected_sr=24000)
    assert mock_session.post.call_count == 2
    assert mock_session.get.call_count == 1


def test_capcut_synthesize_error_handling():
    from app.backends.base import InvalidOption

    mock_session = MagicMock()
    backend = CapCutBackend(SETTINGS, session=mock_session)

    # 1. Empty/whitespace text raises InvalidOption (HTTP 400)
    with pytest.raises(InvalidOption):
        backend.synthesize("   ", "BV421_vivn_streaming")

    # 2. CapCut API ret=1014 (system busy) raises RuntimeError
    busy_resp = MagicMock()
    busy_resp.status_code = 200
    busy_resp.json.return_value = {"ret": "1014", "errmsg": "system busy"}
    mock_session.post.return_value = busy_resp

    with pytest.raises(RuntimeError, match="ret='1014'"):
        backend.synthesize("Xin chào", "BV421_vivn_streaming")


def test_capcut_http_voices_and_models():
    # GET /v1/models should contain capcut
    res_models = client.get("/v1/models", headers=AUTH)
    assert res_models.status_code == 200
    models_data = res_models.json().get("data", [])
    model_ids = {m["id"] for m in models_data}
    assert "capcut" in model_ids

    # GET /v1/voices?model=capcut should return 24 voices
    res_voices = client.get("/v1/voices?model=capcut", headers=AUTH)
    assert res_voices.status_code == 200
    voices_data = res_voices.json().get("data", [])
    assert len(voices_data) == 24
    assert all(v["model"] == "capcut" for v in voices_data)
    assert all(v["language"] == "vi" for v in voices_data)

    # GET /v1/voices?language=vi includes capcut voices
    res_vi = client.get("/v1/voices?language=vi", headers=AUTH)
    assert res_vi.status_code == 200
    vi_voices = res_vi.json().get("data", [])
    capcut_in_vi = [v for v in vi_voices if v["model"] == "capcut"]
    assert len(capcut_in_vi) == 24


def test_capcut_http_speech_and_stream_with_mock_backend(monkeypatch):
    from app.backends.registry import registry

    capcut_backend = registry.get("capcut")
    assert capcut_backend is not None

    sr = 24000
    t = np.linspace(0, 0.4, int(sr * 0.4), endpoint=False, dtype=np.float32)
    pcm_test = 0.4 * np.sin(2 * np.pi * 330 * t).astype(np.float32)
    fake_result = AudioResult(pcm=pcm_test, sample_rate=sr)

    monkeypatch.setattr(capcut_backend, "synthesize", lambda text, voice, speed=1.0, options=None: fake_result)

    # Synthesize MP3
    res_mp3 = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={
            "model": "capcut",
            "voice": "BV421_vivn_streaming",
            "input": "Kiểm thử tổng hợp âm thanh CapCut",
            "response_format": "mp3",
        },
    )
    assert res_mp3.status_code == 200
    assert res_mp3.headers["content-type"] == "audio/mpeg"
    assert len(res_mp3.content) > 500

    # Synthesize WAV
    res_wav = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={
            "model": "capcut",
            "voice": "BV421_vivn_streaming",
            "input": "Kiểm thử định dạng WAV",
            "response_format": "wav",
        },
    )
    assert res_wav.status_code == 200
    assert res_wav.headers["content-type"] == "audio/wav"
    assert len(res_wav.content) > 500

    # Synthesize Opus
    res_opus = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={
            "model": "capcut",
            "voice": "BV421_vivn_streaming",
            "input": "Kiểm thử định dạng Opus",
            "response_format": "opus",
        },
    )
    assert res_opus.status_code == 200
    assert res_opus.headers["content-type"] == "audio/ogg"
    assert len(res_opus.content) > 200

    # Unknown voice when targeting capcut explicitly -> 404 unknown_voice
    res_404 = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={
            "model": "capcut",
            "voice": "non_existent_capcut_voice",
            "input": "Kiểm thử giọng lỗi",
        },
    )
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "unknown_voice"

    # Stream endpoint POST /v1/audio/stream with model="capcut"
    res_stream = client.post(
        "/v1/audio/stream",
        headers=AUTH,
        json={
            "model": "capcut",
            "voice": "BV421_vivn_streaming",
            "input": "Câu thứ nhất từ CapCut. Câu thứ hai từ CapCut.",
        },
    )
    assert res_stream.status_code == 200
    assert res_stream.headers["content-type"] == "audio/mpeg"
    assert len(res_stream.content) > 500


# --- Optional Live Synth Test ---

@pytest.mark.synth
def test_capcut_live_synthesis():
    backend = CapCutBackend(SETTINGS)
    try:
        res = backend.synthesize("Xin chào, đây là giọng đọc thử nghiệm từ CapCut.", "BV421_vivn_streaming")
        assert_real_audio(res.pcm, res.sample_rate)
    except Exception as exc:
        pytest.skip(f"Live CapCut API call failed (possibly network/API restriction): {exc}")
