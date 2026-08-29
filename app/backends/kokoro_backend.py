"""Kokoro-82M v1.0 adapter (English presets) — https://github.com/thewh1teagle/kokoro-onnx.

Torch-free: synthesis runs on onnxruntime via `kokoro-onnx`. English G2P needs
the system package `espeak-ng` (`apt-get install espeak-ng`); a missing one
surfaces as a clear error on the first synth, never as empty audio.

Presets only (no cloning). The shipped `voices-v1.0.bin` holds voices for several
languages; this backend exposes only the 28 English ones (20 US + 8 UK) so the
API never leaks a voice in the wrong language. Like VieNeu, the engine is loaded
lazily on first use and serialised behind one lock (the router caps concurrency).
"""

from __future__ import annotations

import importlib.util
import os
import threading

import numpy as np

from .base import AudioResult, Voice, VoiceBackend

# (voice_id, display name, accent, gender) — sourced from Kokoro-82M VOICES.md.
# `a*` = American English (en-us), `b*` = British English (en-gb).
_EN_VOICES: tuple[tuple[str, str, str, str], ...] = (
    # American English — female
    ("af_heart", "Heart", "US", "nữ"),
    ("af_alloy", "Alloy", "US", "nữ"),
    ("af_aoede", "Aoede", "US", "nữ"),
    ("af_bella", "Bella", "US", "nữ"),
    ("af_jessica", "Jessica", "US", "nữ"),
    ("af_kore", "Kore", "US", "nữ"),
    ("af_nicole", "Nicole", "US", "nữ"),
    ("af_nova", "Nova", "US", "nữ"),
    ("af_river", "River", "US", "nữ"),
    ("af_sarah", "Sarah", "US", "nữ"),
    ("af_sky", "Sky", "US", "nữ"),
    # American English — male
    ("am_adam", "Adam", "US", "nam"),
    ("am_echo", "Echo", "US", "nam"),
    ("am_eric", "Eric", "US", "nam"),
    ("am_fenrir", "Fenrir", "US", "nam"),
    ("am_liam", "Liam", "US", "nam"),
    ("am_michael", "Michael", "US", "nam"),
    ("am_onyx", "Onyx", "US", "nam"),
    ("am_puck", "Puck", "US", "nam"),
    ("am_santa", "Santa", "US", "nam"),
    # British English — female
    ("bf_alice", "Alice", "UK", "nữ"),
    ("bf_emma", "Emma", "UK", "nữ"),
    ("bf_isabella", "Isabella", "UK", "nữ"),
    ("bf_lily", "Lily", "UK", "nữ"),
    # British English — male
    ("bm_daniel", "Daniel", "UK", "nam"),
    ("bm_fable", "Fable", "UK", "nam"),
    ("bm_george", "George", "UK", "nam"),
    ("bm_lewis", "Lewis", "UK", "nam"),
)


class KokoroBackend(VoiceBackend):
    name = "kokoro"

    def __init__(self, settings) -> None:
        self._model_path = settings.kokoro_model_path
        self._voices_path = settings.kokoro_voices_path
        self._default_voice = settings.kokoro_default_voice
        self._engine = None
        self._lock = threading.Lock()
        self._voices_cache: list[Voice] | None = None
        self.supports_cloning = False

    @staticmethod
    def is_available(settings) -> bool:
        """True if `kokoro_onnx` is importable AND both model files exist.

        Takes `settings` (unlike VieNeu's arg-less `is_available`) because
        registration must know the asset paths, not just the package."""
        if importlib.util.find_spec("kokoro_onnx") is None:
            return False
        return os.path.isfile(settings.kokoro_model_path) and os.path.isfile(
            settings.kokoro_voices_path
        )

    def _get_engine(self):
        if self._engine is None:
            from kokoro_onnx import Kokoro

            self._engine = Kokoro(self._model_path, self._voices_path)
        return self._engine

    def list_voices(self) -> list[Voice]:
        if self._voices_cache is None:
            self._voices_cache = [
                Voice(
                    id=vid,
                    name=f"{name} ({accent}, {gender})",
                    model=self.name,
                    language="en",
                )
                for vid, name, accent, gender in _EN_VOICES
            ]
        return self._voices_cache

    def resolve_voice(self, voice: str | None, *, strict: bool = False) -> str | None:
        # Same match order as the base contract, but a lenient miss falls back to
        # the configured preset (af_heart) rather than the table's first entry.
        voices = self.list_voices()
        ids = {v.id for v in voices}
        if voice in ids:
            return voice
        names = {v.name: v.id for v in voices}
        if voice in names:
            return names[voice]
        if strict:
            return None
        return self._default_voice

    def synthesize(
        self, text: str, voice: str, speed: float = 1.0, options: dict | None = None
    ) -> AudioResult:
        # Accent follows the voice prefix: `b*` = British, everything else US.
        lang = "en-gb" if voice.startswith("b") else "en-us"
        engine = self._get_engine()
        try:
            with self._lock:
                samples, sr = engine.create(
                    text, voice=voice, speed=float(speed), lang=lang
                )
        except Exception as exc:  # surface a missing espeak-ng clearly
            msg = str(exc).lower()
            if "espeak" in msg or "phonem" in msg:
                raise RuntimeError(
                    "Kokoro English G2P failed — is `espeak-ng` installed? "
                    "Install it with `apt-get install espeak-ng`. "
                    f"Original error: {exc}"
                ) from exc
            raise
        pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
        return AudioResult(pcm=pcm, sample_rate=int(sr))
