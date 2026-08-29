"""VOICEVOX (Japanese) backend tests.

Fast unit tests (no marker) cover the WAV decode helper + id/allowlist parsing
without the core package. The `synth` tests need the installed wheel + assets
(bash scripts/fetch-voicevox.sh) and skip cleanly when absent. The lazy-load test
proves no VVM is loaded into the synthesizer until a style is actually used.
"""

from __future__ import annotations

import io
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
AUTH = {"Authorization": "Bearer test-key"}

from conftest import assert_real_audio, save_wav  # noqa: E402
from app.backends.voicevox_backend import (  # noqa: E402
    VoicevoxBackend,
    _allowed,
    _decode_wav_f32,
    _parse_allowlist,
    _parse_style_id,
)
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

SETTINGS = get_settings()
client = TestClient(app)

requires_voicevox = pytest.mark.skipif(
    not VoicevoxBackend.is_available(SETTINGS), reason="voicevox assets not installed"
)

JA_TEXT = "こんにちは、世界。今日はいい天気ですね。"


# --- Unit (no core package) ---

def test_decode_wav_f32_roundtrip():
    import soundfile as sf

    sig = (0.2 * np.sin(np.arange(24000) * 0.05)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, sig, 24000, format="WAV", subtype="PCM_16")
    pcm, sr = _decode_wav_f32(buf.getvalue())
    assert sr == 24000
    assert pcm.dtype == np.float32 and pcm.ndim == 1 and len(pcm) == 24000


def test_parse_style_id_accepts_bare_and_uuid_forms():
    assert _parse_style_id("3") == 3
    assert _parse_style_id("7f2e-uuid:47") == 47


def test_allowlist_filtering():
    assert _parse_allowlist("3, u:5 , ") == {"3", "u:5"}
    assert _allowed(set(), "u", 9) is True  # empty = allow all
    assert _allowed({"3"}, "u", 3) is True
    assert _allowed({"3"}, "u", 4) is False
    assert _allowed({"u:4"}, "u", 4) is True


def test_voicevox_is_available_false_without_assets(tmp_path):
    class S:
        voicevox_dict_dir = str(tmp_path / "no_dict")
        voicevox_vvm_dir = str(tmp_path / "no_vvms")

    assert VoicevoxBackend.is_available(S) is False


# --- Synth (needs wheel + dict + VVM) ---

@pytest.mark.synth
@requires_voicevox
def test_voicevox_synthesizes_japanese():
    vb = VoicevoxBackend(SETTINGS)
    voices = vb.list_voices()
    assert voices, "no VOICEVOX voices discovered"
    rendered = []
    for v in voices[:2]:
        res = vb.synthesize(JA_TEXT, v.id)
        assert_real_audio(res.pcm, res.sample_rate)
        save_wav(res.pcm, res.sample_rate, f"voicevox-{v.id}.wav")
        rendered.append(res.pcm)
    if len(rendered) == 2:
        assert not np.array_equal(rendered[0], rendered[1])


@pytest.mark.synth
@requires_voicevox
def test_voicevox_lazy_loads_vvm():
    vb = VoicevoxBackend(SETTINGS)
    vb.list_voices()  # discovery reads metadata only
    assert vb._loaded == set(), "no VVM should be loaded into the synthesizer yet"

    first = vb.list_voices()[0]
    vb.synthesize("テスト", first.id)
    assert len(vb._loaded) == 1
    assert vb._style_to_vvm[int(first.id)] in vb._loaded


@pytest.mark.synth
@requires_voicevox
def test_voicevox_http_and_credit():
    ja = client.get("/v1/voices?language=ja", headers=AUTH).json()["data"]
    assert ja, "no Japanese voices exposed"
    assert any("VOICEVOX" in v["name"] for v in ja), "missing VOICEVOX credit"

    r = client.post(
        "/v1/audio/speech", headers=AUTH,
        json={"model": "voicevox", "voice": ja[0]["id"], "input": "こんにちは", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/wav"
    assert len(r.content) > 44  # more than a bare WAV header
