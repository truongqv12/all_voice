"""The contract every voice backend implements.

Adding a new TTS engine == writing one class here that subclasses
`VoiceBackend` and registering it in `app.main`. Routers, schemas, auth and the
audio encoder are untouched.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Voice:
    """A selectable voice, aggregated into GET /v1/voices."""

    id: str
    name: str
    model: str
    language: str = "vi"
    styles: list[str] = field(default_factory=list)


@dataclass
class AudioResult:
    """Raw synthesis output: mono float32 PCM in [-1, 1] plus its sample rate.

    Backends return PCM only; the shared encoder turns it into the requested
    container/codec (mp3/opus/aac/flac/wav/pcm)."""

    pcm: np.ndarray
    sample_rate: int


class InvalidOption(ValueError):
    """A backend rejects a tuning/enrolment option (bad key or value).

    Raised by a backend that owns a knob (e.g. VieNeu validating `style`, or a
    clone-first engine requiring `ref_text`). The router maps it to 400, keeping
    it distinct from an unexpected error (500)."""


class VoiceBackend(ABC):
    #: Backend id; doubles as the OpenAI-style "model" name in requests.
    name: str
    #: Whether this backend can enrol cloned voices from an audio sample.
    supports_cloning: bool = False

    @abstractmethod
    def list_voices(self) -> list[Voice]:
        """Voices this backend can render (presets + any enrolled clones)."""

    @abstractmethod
    def synthesize(
        self, text: str, voice: str, speed: float = 1.0, options: dict | None = None
    ) -> AudioResult:
        """Render `text` with `voice` into PCM.

        `options` carries backend tuning knobs (currently just `style`). A
        backend maps the keys it understands and ignores the rest."""

    def register_voice(
        self,
        voice_id: str,
        name: str,
        sample_path: str,
        *,
        denoise: bool = True,
        use_ref_codes: bool = True,
        options: dict | None = None,
    ) -> None:
        """Enrol a cloned voice from a reference audio file (cloning backends).

        `denoise` cleans the reference (leave on for noisy clips, turn off for
        already-clean samples to preserve timbre); `use_ref_codes` anchors
        prosody/timbre with reference codes. `options` carries engine-specific
        enrolment params (e.g. a clone-first engine's `ref_text`); a backend
        raises `InvalidOption` for a required option it is missing and ignores
        knobs it lacks."""
        raise NotImplementedError(f"Backend '{self.name}' does not support voice cloning")

    def remove_voice(self, voice_id: str) -> bool:
        """Drop a previously enrolled cloned voice.

        Returns True if this backend was holding that clone (so callers can
        clean up voices that linger in memory but no longer have a store
        record), False if it did not know the id."""
        raise NotImplementedError(f"Backend '{self.name}' does not support voice cloning")

    def resolve_voice(self, voice: str | None, *, strict: bool = False) -> str | None:
        """Map a requested voice to a real one this backend owns.

        `strict` (set when the client named this backend explicitly): an unknown
        voice returns None so the router can 404 instead of silently guessing.
        Non-strict (the request used an OpenAI-generic model like `tts-1` that
        fell back to the default backend): an unknown/absent voice (e.g.
        "alloy") falls back to the first preset, preserving drop-in
        compatibility."""
        voices = self.list_voices()
        if not voices:
            raise RuntimeError(f"Backend '{self.name}' exposes no voices")
        ids = {v.id for v in voices}
        if voice in ids:
            return voice
        names = {v.name: v.id for v in voices}
        if voice in names:
            return names[voice]
        if strict:
            return None
        return voices[0].id
