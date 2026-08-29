"""Readiness oracle: pins the behaviour the multi-engine refactor must preserve.

These are the *invariants* — assertions that must hold both before and after the
seams are opened (routing gate, options gate, cloning readiness, discovery
filter). Phase 6 re-runs this exact file to prove no regression.

Behaviour that changes *on purpose* (e.g. a known model + unknown voice moving
from 200 to 404) is pinned in the phase that changes it, never here, so this
baseline stays green throughout the refactor.

Slow tests (real synthesis / clone enrolment) carry the `synth` marker; run
`-m "not synth"` for a fast dev loop (`-m` filters by marker; `-k` would also
catch tests whose names merely contain "synth").
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
AUTH = {"Authorization": "Bearer test-key"}

from app.main import app  # noqa: E402  (import after env is set)

client = TestClient(app)

SAMPLE = (Path(__file__).parent / "clone_1.wav").read_bytes()


def test_baseline_models_lists_vieneu():
    body = client.get("/v1/models", headers=AUTH).json()
    assert body["object"] == "list"
    assert "vieneu" in [m["id"] for m in body["data"]]


def test_baseline_voices_shape_and_language():
    r = client.get("/v1/voices", headers=AUTH)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) > 0
    for v in data:
        assert {"id", "name", "model", "language", "styles"} <= v.keys()
        assert v["model"] and v["language"]
        # VieNeu presets are Vietnamese. Optional engines (kokoro/voicevox) may
        # also be registered when their assets are installed, so assert language
        # per known model rather than pinning a single-engine baseline.
        if v["model"] == "vieneu":
            assert v["language"] == "vi"
    # VieNeu is always registered (a base dependency).
    assert any(v["model"] == "vieneu" and v["language"] == "vi" for v in data)


@pytest.mark.synth
def test_baseline_openai_dropin_alias():
    # Stock OpenAI SDK: unknown model + unknown voice must fall back, not error.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "tts-1", "input": "Xin chào.", "voice": "alloy", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


@pytest.mark.synth
def test_baseline_style_valid_and_invalid():
    # A valid style synthesizes; an invalid one is rejected with 400. The 400 is
    # the invariant — Phase 3 moves the check from the schema down to the
    # backend, but the *status* stays 400.
    ok = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "Kể chuyện nhé.", "voice": "Trúc Ly",
              "response_format": "wav", "style": "doc_truyen"},
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.content) > 0

    bad = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "x", "voice": "Trúc Ly", "style": "opera"},
    )
    assert bad.status_code == 400


@pytest.mark.synth
def test_baseline_clone_appears_in_both_lists():
    # Enrol with no `model` (default backend) and assert the *shape*: the clone
    # shows up in both the OpenAI list and the merged /v1/voices. Heavy synth of
    # the clone is already covered in test_e2e; here we only pin discovery.
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("sample.wav", SAMPLE, "audio/wav")},
        data={"name": "Readiness Clone"},
    )
    assert created.status_code == 200, created.text
    voice_id = created.json()["id"]
    try:
        listed = client.get("/v1/audio/voices", headers=AUTH).json()["data"]
        assert voice_id in [v["id"] for v in listed]
        merged = client.get("/v1/voices", headers=AUTH).json()["data"]
        assert voice_id in [v["id"] for v in merged]
    finally:
        client.delete(f"/v1/audio/voices/{voice_id}", headers=AUTH)


# --- Phase 2: routing gate (strict/lenient) — intentional behaviour change ---


def test_gate_known_model_unknown_voice_404():
    # Explicit, registered model + a voice it does not own -> 404 (no silent
    # fallback). This replaces the old 200-preset-fallback for known models.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "x", "voice": "khong_ton_tai_123"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "unknown_voice"


@pytest.mark.synth
def test_gate_unknown_model_alias_still_200():
    # OpenAI-generic model stays lenient (drop-in preserved).
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "tts-1", "input": "Xin chào.", "voice": "alloy", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


@pytest.mark.synth
def test_gate_known_model_real_voice_200():
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "Xin chào.", "voice": "Trúc Ly", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


# --- Phase 3: input options gate ---


def test_options_style_invalid_400_from_backend():
    # `style` is free-form in the schema now; VieNeu rejects an unknown value
    # (InvalidOption -> 400 invalid_option). The 400 status is the invariant.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "x", "voice": "Trúc Ly", "style": "opera"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_option"


@pytest.mark.synth
def test_options_extra_passthrough_ignored():
    # Unknown `extra` keys pass through and are safely ignored by VieNeu.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "Xin chào.", "voice": "Trúc Ly",
              "response_format": "wav", "style": "tu_nhien",
              "extra": {"foo": 1, "speedScale": 1.2}},
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


# --- Phase 4: cloning multi-engine readiness ---


@pytest.mark.synth
def test_clone_default_model_unchanged():
    # No `model`/`ref_text` -> identical to the pre-refactor default path.
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("s.wav", SAMPLE, "audio/wav")},
        data={"name": "Default Model Clone"},
    )
    assert created.status_code == 200, created.text
    client.delete(f"/v1/audio/voices/{created.json()['id']}", headers=AUTH)


@pytest.mark.synth
def test_clone_explicit_model_vieneu():
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("s.wav", SAMPLE, "audio/wav")},
        data={"name": "Explicit VieNeu", "model": "vieneu"},
    )
    assert created.status_code == 200, created.text
    client.delete(f"/v1/audio/voices/{created.json()['id']}", headers=AUTH)


def test_clone_unknown_model_400():
    # An unregistered model is rejected explicitly (not enrolled into default).
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("s.wav", SAMPLE, "audio/wav")},
        data={"name": "Bad Model", "model": "no-such-backend"},
    )
    assert created.status_code == 400
    assert created.json()["error"]["code"] == "model_not_found"


@pytest.mark.synth
def test_clone_ref_text_ignored_by_vieneu():
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("s.wav", SAMPLE, "audio/wav")},
        data={"name": "Ref Text VieNeu", "ref_text": "hello there"},
    )
    assert created.status_code == 200, created.text
    client.delete(f"/v1/audio/voices/{created.json()['id']}", headers=AUTH)


def test_voice_store_persists_enrol_options(tmp_path):
    # Unit test (no HTTP): enrol_options round-trips, and an old record missing
    # the key still loads with an empty default.
    import json

    from app.voice_store import VoiceRecord, VoiceStore

    store = VoiceStore(tmp_path)
    rec = store.create(
        name="X", sample=b"data", suffix=".wav", backend="faketts",
        enrol_options={"ref_text": "xin chào"},
    )
    raw = json.loads((tmp_path / "registry.json").read_text(encoding="utf-8"))
    assert raw[0]["enrol_options"] == {"ref_text": "xin chào"}

    reloaded = VoiceStore(tmp_path).get(rec.id)
    assert reloaded.enrol_options == {"ref_text": "xin chào"}

    old = VoiceRecord(
        id="v_old", name="Old", created_at=0, backend="vieneu",
        sample_path=str(tmp_path / "s.wav"),
    )
    assert old.enrol_options == {}


# --- Phase 5: voice discovery filter (additive) ---


def test_voices_filter_by_model():
    data = client.get("/v1/voices?model=vieneu", headers=AUTH).json()["data"]
    assert len(data) > 0
    assert all(v["model"] == "vieneu" for v in data)


def test_voices_filter_by_language():
    data = client.get("/v1/voices?language=vi", headers=AUTH).json()["data"]
    assert len(data) > 0
    assert all(v["language"] == "vi" for v in data)


def test_voices_filter_unknown_returns_empty():
    # A model that is never a registered backend yields an empty list, not error.
    r = client.get("/v1/voices?model=no-such-backend", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_voices_no_filter_unchanged():
    # No filter returns at least every VieNeu voice (plus any optional engine's
    # voices that happen to be registered).
    data = client.get("/v1/voices", headers=AUTH).json()["data"]
    vieneu = client.get("/v1/voices?model=vieneu", headers=AUTH).json()["data"]
    assert len(vieneu) > 0
    ids = {v["id"] for v in data}
    assert {v["id"] for v in vieneu} <= ids
    assert len(data) >= len(vieneu)
