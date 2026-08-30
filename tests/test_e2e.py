"""End-to-end API test: boots the app in-process (real VieNeu backend) and
exercises every endpoint, including a real synthesis for each audio format."""

from __future__ import annotations

import io
import os
from pathlib import Path

import av
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


def test_openapi_reports_application_version():
    schema = client.get("/openapi.json").json()

    assert schema["info"]["version"] == "0.1.1"


def test_public_discovery_and_clone_guard():
    # Discovery is public (Stage-1 anon share): no key needed to see models/voices.
    assert client.get("/v1/models").status_code == 200
    assert client.get("/v1/voices").status_code == 200
    # Clone CRUD stays key-guarded even with anon TTS/ASR open.
    assert client.get("/v1/audio/voices").status_code == 401
    created = client.post(
        "/v1/audio/voices",
        files={"audio_sample": ("s.wav", b"RIFFxxxx", "audio/wav")},
        data={"name": "NoKey"},
    )
    assert created.status_code == 401
    assert "error" in created.json()


def test_openapi_uses_bearer_security_scheme():
    schema = app.openapi()
    bearer = schema["components"]["securitySchemes"]["BearerAuth"]

    assert bearer["type"] == "http"
    assert bearer["scheme"] == "bearer"
    # Public routes carry no bearer requirement: the voice-preview endpoint (a
    # browser <audio src> plays it with no header) and Stage-1 discovery
    # (/v1/voices, /v1/models are open so anon clients can list before choosing).
    # Anon TTS/ASR/stream still DECLARE the optional bearer scheme (a valid key is
    # the higher TRUSTED tier), so they keep the requirement in the schema.
    public_paths = {
        "/v1/voices/{model}/{voice_id}/preview",
        "/v1/voices",
        "/v1/models",
    }
    for path, path_item in schema["paths"].items():
        if not path.startswith("/v1/"):
            continue
        for operation in path_item.values():
            if path not in public_paths:
                assert {"BearerAuth": []} in operation["security"]
            # No route may declare an Authorization header parameter (the bearer
            # scheme, or the preview handler's manual check, owns that header).
            assert not any(
                parameter.get("in") == "header"
                and parameter.get("name", "").lower() == "authorization"
                for parameter in operation.get("parameters", [])
            )

    assert "security" not in schema["paths"]["/health"]["get"]


def test_openapi_declares_audio_responses_as_binary():
    content = app.openapi()["paths"]["/v1/audio/speech"]["post"]["responses"]["200"][
        "content"
    ]
    audio_types = {
        "audio/mpeg",
        "audio/ogg",
        "audio/aac",
        "audio/flac",
        "audio/wav",
        "audio/pcm",
    }

    assert audio_types == set(content)
    for media_type in audio_types:
        assert content[media_type]["schema"] == {"type": "string", "format": "binary"}


def test_swagger_docs_install_audio_response_plugin():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui-dist@5.32.6" in response.text
    assert "AudioResponsePlugin" in response.text
    assert "URL.createObjectURL" in response.text
    assert "plugins: [AudioResponsePlugin]" in response.text
    assert "__OPENAPI_URL__" not in response.text
    assert "/docs" not in app.openapi()["paths"]
    assert client.get("/redoc").status_code == 200


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
    if fmt != "pcm":
        with av.open(io.BytesIO(r.content)) as container:
            assert sum(frame.samples for frame in container.decode(audio=0)) > 0


def test_openai_alias():
    # Unknown OpenAI model + voice must fall back, not error.
    r = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "tts-1", "input": "Xin chào.", "voice": "alloy", "response_format": "wav"},
    )
    assert r.status_code == 200, r.text
    assert len(r.content) > 0


def test_speed_accepted_but_noop():
    # `speed` stays in the schema for OpenAI-SDK compatibility, but VieNeu has no
    # native speed control and the gateway no longer time-stretches, so any
    # in-range value is simply accepted and returns valid audio.
    text = "Đây là câu kiểm tra tốc độ đọc của hệ thống."
    for speed in (0.5, 1.0, 2.0):
        r = client.post("/v1/audio/speech", headers=AUTH,
                        json={"model": "vieneu", "input": text, "voice": "Trúc Ly",
                              "response_format": "wav", "speed": speed})
        assert r.status_code == 200, r.text
        assert len(r.content) > 44  # more than a bare WAV header


def test_tuning_options():
    # `style` is the only exposed knob; it is accepted.
    ok = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={
            "model": "vieneu", "input": "Kể chuyện nhé.", "voice": "Trúc Ly",
            "response_format": "wav", "style": "doc_truyen",
        },
    )
    assert ok.status_code == 200, ok.text
    assert len(ok.content) > 0

    # An invalid style value is rejected with 400.
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


def test_delete_voice_persisted_by_another_worker():
    # Simulate a record written to registry.json by a different worker/instance
    # after this process started: it is on disk but not in our in-memory cache.
    # The store must re-read disk so the delete still finds and removes it.
    import json

    from app.voice_store import voice_store

    other_id = "voice_otherworker0000000000ab"
    raw = json.loads(voice_store.index_path.read_text(encoding="utf-8")) \
        if voice_store.index_path.exists() else []
    raw.append({
        "id": other_id, "name": "From Worker B", "created_at": 0,
        "backend": "vieneu", "sample_path": "data/voices/samples/missing.wav",
        "denoise": True, "use_ref_codes": True,
    })
    voice_store.index_path.write_text(json.dumps(raw), encoding="utf-8")
    assert other_id not in voice_store._records  # truly stale in memory

    deleted = client.delete(f"/v1/audio/voices/{other_id}", headers=AUTH)
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert client.get(f"/v1/audio/voices/{other_id}", headers=AUTH).status_code == 404


def test_delete_backend_orphan_without_store_record():
    # A clone that lingers only in a backend's memory (no store record) must
    # still be deletable — a voice you can see is a voice you can delete.
    from app.backends.registry import registry
    from app.voice_store import voice_store

    backend = registry.get("vieneu")
    orphan_id = "voice_orphaninmemory00000000cd"
    backend._custom[orphan_id] = "Ghost"
    assert voice_store.get(orphan_id) is None

    deleted = client.delete(f"/v1/audio/voices/{orphan_id}", headers=AUTH)
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True
    assert orphan_id not in backend._custom


def test_voice_consent_stub():
    r = client.post(
        "/v1/audio/voice_consents",
        headers=AUTH,
        files={"recording": ("c.wav", b"RIFFxxxx", "audio/wav")},
        data={"language": "vi-VN", "name": "consent"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"].startswith("cons_")


def test_custom_voice_id_lifecycle():
    sample = (Path(__file__).parent / "clone_1.wav").read_bytes()
    custom_id = "voice_mc_test_custom"

    # 1. Enrol with custom ID
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("sample.wav", sample, "audio/wav")},
        data={"name": "MC Custom", "id": custom_id},
    )
    assert created.status_code == 200, created.text
    assert created.json()["id"] == custom_id
    assert created.json()["name"] == "MC Custom"

    # 2. Overwrite the same custom ID with an updated name
    updated = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("sample.wav", sample, "audio/wav")},
        data={"name": "MC Custom V2", "id": custom_id},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == custom_id
    assert updated.json()["name"] == "MC Custom V2"

    # 3. Retrieve and verify name updated
    retrieved = client.get(f"/v1/audio/voices/{custom_id}", headers=AUTH)
    assert retrieved.status_code == 200
    assert retrieved.json()["name"] == "MC Custom V2"

    # 4. Synthesize with custom ID
    spoken = client.post(
        "/v1/audio/speech",
        headers=AUTH,
        json={"model": "vieneu", "input": "Kiểm tra giọng tùy chỉnh.", "voice": custom_id, "response_format": "wav"},
    )
    assert spoken.status_code == 200, spoken.text
    assert len(spoken.content) > 0

    # 5. Clean up
    deleted = client.delete(f"/v1/audio/voices/{custom_id}", headers=AUTH)
    assert deleted.status_code == 200 and deleted.json()["deleted"] is True


def test_invalid_voice_id():
    sample = (Path(__file__).parent / "clone_1.wav").read_bytes()
    bad = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("sample.wav", sample, "audio/wav")},
        data={"name": "Bad ID", "id": "invalid voice id with spaces!"},
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "invalid_voice_id"


def test_no_duplicate_voices_after_cloning():
    sample = (Path(__file__).parent / "clone_1.wav").read_bytes()
    vid = "voice_dedup_test"
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("sample.wav", sample, "audio/wav")},
        data={"name": "Dedup Display Name", "id": vid},
    )
    assert created.status_code == 200

    # Query /v1/voices and verify vid only appears ONCE with its display name
    all_voices = client.get("/v1/voices", headers=AUTH).json()["data"]
    matches = [v for v in all_voices if v["id"] == vid]
    assert len(matches) == 1
    assert matches[0]["name"] == "Dedup Display Name"

    # Clean up
    client.delete(f"/v1/audio/voices/{vid}", headers=AUTH)


