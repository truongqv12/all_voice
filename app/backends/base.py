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
    ) -> None:
        """Enrol a cloned voice from a reference audio file (cloning backends).

        `denoise` cleans the reference (leave on for noisy clips, turn off for
        already-clean samples to preserve timbre); `use_ref_codes` anchors
        prosody/timbre with reference codes. A backend ignores knobs it lacks."""
        raise NotImplementedError(f"Backend '{self.name}' does not support voice cloning")

    def remove_voice(self, voice_id: str) -> bool:
        """Drop a previously enrolled cloned voice.

        Returns True if this backend was holding that clone (so callers can
        clean up voices that linger in memory but no longer have a store
        record), False if it did not know the id."""
        raise NotImplementedError(f"Backend '{self.name}' does not support voice cloning")

    def resolve_voice(self, voice: str | None) -> str:
        """Map a requested voice to a real one this backend owns.

        Enables drop-in OpenAI compatibility: an unknown or absent voice name
        (e.g. "alloy") falls back to this backend's first preset instead of
        erroring."""
        voices = self.list_voices()
        if not voices:
            raise RuntimeError(f"Backend '{self.name}' exposes no voices")
        ids = {v.id for v in voices}
        if voice in ids:
            return voice
        names = {v.name: v.id for v in voices}
        if voice in names:
            return names[voice]
        return voices[0].id
