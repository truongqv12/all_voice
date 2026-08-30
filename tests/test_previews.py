"""Voice preview ("nghe thử") tests.

Fast lane uses `FakeBackend` (instant, deterministic silent synth — no model
load) plus an isolated `previews_dir` under `tmp_path`, so nothing touches the
real `data/previews`. One `-m synth` test proves a real VieNeu preview is valid
non-silent 48000 Hz audio.
"""

from __future__ import annotations

import base64
import inspect
import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEYS", "test-key")
os.environ.setdefault("PREVIEW_WARM_ON_STARTUP", "false")
AUTH = {"Authorization": "Bearer test-key"}

from app import previews  # noqa: E402
from app.backends.base import AudioResult, InvalidOption, Voice, VoiceBackend  # noqa: E402
from app.backends.registry import registry  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402  (import after env is set)
from app.voice_store import voice_store  # noqa: E402

client = TestClient(app)
SAMPLE = (Path(__file__).parent / "clone_1.wav").read_bytes()


class FakeBackend(VoiceBackend):
    """Minimal second engine: Japanese preset, clone-first (requires ref_text).

    Synthesis returns 1s of silence — instant + deterministic, so the fast lane
    never loads a real model."""

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
        return AudioResult(pcm=np.zeros(16000, dtype=np.float32), sample_rate=16000)

    def register_voice(self, voice_id, name, sample_path, *,
                       denoise=True, use_ref_codes=True, options=None) -> None:
        if not (options or {}).get("ref_text"):
            raise InvalidOption("faketts requires ref_text to clone")
        self._clones[voice_id] = name

    def remove_voice(self, voice_id) -> bool:
        return self._clones.pop(voice_id, None) is not None


@pytest.fixture
def previews_tmp(tmp_path, monkeypatch):
    """Point previews_dir at an isolated tmp dir (monkeypatch auto-reverts)."""
    s = get_settings()  # lru-cached singleton
    monkeypatch.setattr(s, "previews_dir", str(tmp_path / "previews"))
    yield tmp_path


@pytest.fixture
def with_fake_backend():
    """Register FakeBackend beside VieNeu (which stays default), then clean up
    the registry and any clone records persisted under faketts."""
    registry.register(FakeBackend())
    try:
        yield
    finally:
        registry._backends.pop("faketts", None)
        for rec in voice_store.list():
            if rec.backend == "faketts":
                voice_store.delete(rec.id)


def _enrol_clone(name: str = "Cloned JA") -> str:
    created = client.post(
        "/v1/audio/voices",
        headers=AUTH,
        files={"audio_sample": ("s.wav", SAMPLE, "audio/wav")},
        data={"name": name, "model": "faketts", "ref_text": "テスト"},
    )
    assert created.status_code == 200, created.text
    return created.json()["id"]


# --- Fast tests (FakeBackend synth is instant; no `synth` mark) ---------------


def test_voices_carry_preview_url(previews_tmp, with_fake_backend):
    data = client.get("/v1/voices", headers=AUTH).json()["data"]
    assert data and all(v["preview_url"] for v in data)
    assert all(v["preview_base64"] is None for v in data)
    fake = next(v for v in data if v["model"] == "faketts")
    assert fake["preview_url"] == "/v1/voices/faketts/ja_1/preview"


def test_preset_preview_public(previews_tmp, with_fake_backend):
    # No AUTH header -> a preset preview must still serve (browser <audio src>).
    r = client.get("/v1/voices/faketts/ja_1/preview")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/mpeg"
    assert "public" in r.headers["cache-control"]
    assert len(r.content) > 0


def test_clone_preview_requires_key(previews_tmp, with_fake_backend):
    vid = _enrol_clone()
    previews.ensure_preview("faketts", vid)  # warm deterministically

    no_key = client.get(f"/v1/voices/faketts/{vid}/preview")
    assert no_key.status_code == 401
    assert no_key.json()["error"]["code"] == "invalid_api_key"

    with_key = client.get(f"/v1/voices/faketts/{vid}/preview", headers=AUTH)
    assert with_key.status_code == 200, with_key.text
    assert "no-store" in with_key.headers["cache-control"]


def test_clone_preview_stays_keyed_when_store_record_gone(previews_tmp, with_fake_backend):
    # Divergence: the cached clone artifact persists (sidecar marks it a clone) but
    # the live voice_store record is gone (e.g. a multi-worker delete, or an
    # orphan). The route must fail closed and still demand a key — never serve the
    # cloned-voice audio publicly.
    vid = _enrol_clone()
    previews.ensure_preview("faketts", vid)  # warm -> sidecar is_clone=True
    assert previews.sidecar_marks_clone("faketts", vid)

    voice_store.delete(vid)  # drop the store record only; artifact + backend entry remain
    assert voice_store.get(vid) is None

    no_key = client.get(f"/v1/voices/faketts/{vid}/preview")
    assert no_key.status_code == 401, no_key.text

    with_key = client.get(f"/v1/voices/faketts/{vid}/preview", headers=AUTH)
    assert with_key.status_code == 200, with_key.text
    assert "no-store" in with_key.headers["cache-control"]


def test_base64_cached_only(previews_tmp, with_fake_backend):
    # Cold cache: the list call must NOT synthesize -> base64 is null.
    cold = client.get("/v1/voices?preview=base64&model=faketts", headers=AUTH).json()["data"]
    ja1 = next(v for v in cold if v["id"] == "ja_1")
    assert ja1["preview_base64"] is None

    previews.ensure_preview("faketts", "ja_1")  # warm
    warm = client.get("/v1/voices?preview=base64&model=faketts", headers=AUTH).json()["data"]
    ja1 = next(v for v in warm if v["id"] == "ja_1")
    assert ja1["preview_base64"] is not None

    served = client.get("/v1/voices/faketts/ja_1/preview").content
    assert base64.b64decode(ja1["preview_base64"]) == served


def test_unknown_voice_404(previews_tmp, with_fake_backend):
    ghost = client.get("/v1/voices/faketts/ghost/preview")
    assert ghost.status_code == 404
    assert ghost.json()["error"]["code"] == "preview_not_found"

    unknown_model = client.get("/v1/voices/nope/x/preview")
    assert unknown_model.status_code == 404

    # A failed lookup must write nothing to disk.
    assert not list((previews_tmp / "previews").rglob("*")) if (previews_tmp / "previews").exists() else True


def test_delete_removes_preview_and_sidecar(previews_tmp, with_fake_backend):
    vid = _enrol_clone()
    previews.ensure_preview("faketts", vid)  # warm
    mp3 = previews.preview_path("faketts", vid)
    sidecar = previews._sidecar_path(mp3)
    assert mp3.exists() and sidecar.exists()

    deleted = client.delete(f"/v1/audio/voices/{vid}", headers=AUTH)
    assert deleted.status_code == 200, deleted.text
    assert not mp3.exists() and not sidecar.exists()


def test_staleness_regen(previews_tmp, with_fake_backend, monkeypatch):
    previews.ensure_preview("faketts", "ja_1")
    mp3 = previews.preview_path("faketts", "ja_1")
    old_hash = previews._read_sidecar(mp3)["text_hash"]

    monkeypatch.setattr(get_settings(), "preview_text_ja", "まったく違うサンプル文です。")
    # is_current is now false -> the endpoint regenerates on next GET.
    assert not previews.is_current(mp3)
    r = client.get("/v1/voices/faketts/ja_1/preview")
    assert r.status_code == 200, r.text
    new_hash = previews._read_sidecar(mp3)["text_hash"]
    assert new_hash != old_hash


def test_prune_orphans(previews_tmp, with_fake_backend):
    # A stray preview whose voice no longer exists must be reaped.
    stray = previews.preview_path("faketts", "zzz_gone")
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"stale")
    previews._write_sidecar(stray, {
        "text_hash": "x", "language": "ja", "style": "",
        "format": "mp3", "voice_id": "zzz_gone", "model": "faketts",
    })
    assert stray.exists()

    previews.prune_orphans()
    assert not stray.exists()
    assert not previews._sidecar_path(stray).exists()


def test_atomic_tmp_unique():
    # Guards the multi-worker collision fix: tmp name carries pid + uuid.
    src = inspect.getsource(previews._atomic_write)
    assert "getpid" in src and "uuid" in src


def test_passage_language_selection():
    assert previews.passage_for("ja") != previews.passage_for("vi")
    assert previews.passage_for("en") != previews.passage_for("vi")
    # Unknown language falls back to the vi passage (default backend's language).
    assert previews.passage_for("xx") == previews.passage_for("vi")


# --- Synth test (real VieNeu; slow) -------------------------------------------


@pytest.mark.synth
def test_real_preset_preview_is_audio(previews_tmp):
    import av

    vieneu_voices = [v for v in registry.all_voices() if v.model == "vieneu"]
    assert vieneu_voices, "no vieneu preset voices registered"
    voice_id = vieneu_voices[0].id

    path = previews.ensure_preview("vieneu", voice_id, force=True)
    assert path is not None and path.exists()

    container = av.open(str(path))
    stream = container.streams.audio[0]
    sr = stream.rate
    samples = [frame.to_ndarray().reshape(-1) for frame in container.decode(stream)]
    container.close()
    pcm = np.concatenate(samples).astype(np.float32)

    assert sr == 48000, f"expected 48000 Hz preview, got {sr}"
    assert len(pcm) > 0.5 * sr, f"preview too short: {len(pcm)} samples at {sr}Hz"
    rms = float(np.sqrt(np.mean(np.square(pcm))))
    assert rms > 1e-3, f"preview looks silent: rms={rms:.2e}"
