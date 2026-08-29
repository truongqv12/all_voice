"""Readiness proof: a second backend plugs into every seam without touching the
core (routers/encoder/auth/schemas).

`FakeBackend` stands in for a future engine (a Japanese, clone-first one like
F5). It never loads a model — synthesis returns deterministic silent PCM — so
these tests are fast and deterministic. If proving any property here required
editing `app/**`, that seam is not open enough and the fix belongs in the
relevant phase, not here.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
AUTH = {"Authorization": "Bearer test-key"}

from app.backends.base import AudioResult, InvalidOption, Voice, VoiceBackend  # noqa: E402
from app.backends.kokoro_backend import KokoroBackend  # noqa: E402
from app.backends.registry import registry  # noqa: E402
from app.backends.voicevox_backend import VoicevoxBackend  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402  (import after env is set)
from app.voice_store import voice_store  # noqa: E402

client = TestClient(app)
SAMPLE = (Path(__file__).parent / "clone_1.wav").read_bytes()
SETTINGS = get_settings()


def test_real_engines_registered_when_assets_present():
    """VieNeu always registers; Kokoro/VOICEVOX join when their assets exist —
    each in its own language, with VieNeu staying the default backend."""
    ids = {m["id"] for m in client.get("/v1/models", headers=AUTH).json()["data"]}
    assert "vieneu" in ids

    if KokoroBackend.is_available(SETTINGS):
        assert "kokoro" in ids
        en = client.get("/v1/voices?language=en", headers=AUTH).json()["data"]
        assert len(en) == 28 and all(v["model"] == "kokoro" for v in en)

    if VoicevoxBackend.is_available(SETTINGS):
        assert "voicevox" in ids
        ja = client.get("/v1/voices?language=ja", headers=AUTH).json()["data"]
        assert ja and any("VOICEVOX" in v["name"] for v in ja)


class FakeBackend(VoiceBackend):
    """Minimal second engine: Japanese preset, clone-first (requires ref_text)."""

    name = "faketts"
    supports_cloning = True

    def __init__(self) -> None:
        self._clones: dict[str, str] = {}

    def list_voices(self) -> list[Voice]:
        base = [Voice(id="ja_1", name="Yuki", model=self.name, language="ja")]
        clones = [
            Voice(id=vid, name=name, model=self.name, language="ja")
            for vid, name in self._clones.items()
        ]
        return base + clones

    def synthesize(self, text, voice, speed=1.0, options=None) -> AudioResult:
        # 1s of silence — enough for the encoder to produce a valid container.
        return AudioResult(pcm=np.zeros(16000, dtype=np.float32), sample_rate=16000)

    def register_voice(self, voice_id, name, sample_path, *,
                       denoise=True, use_ref_codes=True, options=None) -> None:
        if not (options or {}).get("ref_text"):
            raise InvalidOption("faketts requires ref_text to clone")
        self._clones[voice_id] = name

    def remove_voice(self, voice_id) -> bool:
        return self._clones.pop(voice_id, None) is not None


@pytest.fixture
def with_fake_backend():
    """Register FakeBackend beside VieNeu (which stays default), then clean up.

    The registry is a process-wide singleton, so teardown must remove faketts —
    and purge any clone records persisted under it — so nothing leaks into other
    tests or a later app restart."""
    registry.register(FakeBackend())
    try:
        yield
    finally:
        registry._backends.pop("faketts", None)
        for rec in voice_store.list():
            if rec.backend == "faketts":
                voice_store.delete(rec.id)


def test_second_backend_appears_in_models(with_fake_backend):
    ids = [m["id"] for m in client.get("/v1/models", headers=AUTH).json()["data"]]
    assert "faketts" in ids


def test_second_backend_voices_and_filter(with_fake_backend):
    all_voices = client.get("/v1/voices", headers=AUTH).json()["data"]
    assert any(v["language"] == "ja" and v["model"] == "faketts" for v in all_voices)

    by_model = client.get("/v1/voices?model=faketts", headers=AUTH).json()["data"]
    assert by_model and all(v["model"] == "faketts" for v in by_model)

    by_lang = client.get("/v1/voices?language=ja", headers=AUTH).json()["data"]
    assert by_lang and all(v["language"] == "ja" for v in by_lang)


def test_second_backend_routes_to_its_own_synth(with_fake_backend):
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "faketts", "voice": "ja_1", "input": "こんにちは", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/wav"
    assert len(r.content) > 44  # more than a bare WAV header


def test_strict_gate_rejects_cross_backend_voice(with_fake_backend):
    # A vieneu voice requested against faketts -> 404, never silently synthesized
    # in the wrong language.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "faketts", "voice": "Trúc Ly", "input": "x"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "unknown_voice"


@pytest.mark.synth
def test_lenient_dropin_still_routes_to_default(with_fake_backend):
    # Adding a second backend must not break OpenAI drop-in via the default.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "tts-1", "voice": "alloy", "input": "Xin chào.", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


def test_second_backend_cloning_with_ref_text(with_fake_backend):
    # ref_text passthrough + backend-side validation, across the real enrol flow.
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("s.wav", SAMPLE, "audio/wav")},
        data={"name": "Cloned JA", "model": "faketts", "ref_text": "テスト"},
    )
    assert created.status_code == 200, created.text
    vid = created.json()["id"]
    try:
        merged = client.get("/v1/voices?model=faketts", headers=AUTH).json()["data"]
        assert vid in [v["id"] for v in merged]

        spoken = client.post(
            "/v1/audio/speech",
            headers=AUTH,
            json={"model": "faketts", "voice": vid, "input": "テスト", "response_format": "wav"},
        )
        assert spoken.status_code == 200, spoken.text
    finally:
        client.delete(f"/v1/audio/voices/{vid}", headers=AUTH)


def test_second_backend_cloning_missing_ref_text_400(with_fake_backend):
    # Clone-first engine rejects enrolment without ref_text (InvalidOption -> 400).
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("s.wav", SAMPLE, "audio/wav")},
        data={"name": "No Ref Text", "model": "faketts"},
    )
    assert created.status_code == 400
    # enrolment failure is surfaced as a 400 (no dangling store record)
    assert created.json()["error"]["code"] in {"voice_enrolment_failed", "invalid_option"}


def test_second_backend_synth_with_extra(with_fake_backend):
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "faketts", "voice": "ja_1", "input": "x",
              "response_format": "wav", "extra": {"speedScale": 1.5}},
    )
    assert r.status_code == 200, r.text
