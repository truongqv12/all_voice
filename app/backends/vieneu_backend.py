"""VieNeu-TTS adapter (https://github.com/pnnbao97/VieNeu-TTS).

Engine strategy — one VieNeu engine serves both preset synthesis and voice
cloning:

- CPU (default): the ONNX engine. Preset synthesis is fully torch-free. Cloning
  is available only when PyTorch is installed — enrolling a clone runs VieNeu's
  speaker encoder, which uses torch for feature preprocessing even on the ONNX
  engine (the v3-Turbo model ships with speaker embeddings enabled).
- CUDA: a single PyTorch engine serves everything (fast on GPU); install the
  `clone` extra (torch) and set DEVICE=cuda.

VieNeu is not thread-safe, so all synthesis is serialised behind one lock; the
router already caps overall concurrency."""

from __future__ import annotations

import importlib.util
import threading

import numpy as np

from .base import AudioResult, Voice, VoiceBackend


def _torch_available() -> bool:
    return importlib.util.find_spec("torch") is not None


class VieNeuBackend(VoiceBackend):
    name = "vieneu"

    def __init__(self, device: str = "cpu") -> None:
        self._device = device
        self._engine = None
        self._lock = threading.Lock()
        self._presets_cache: list[Voice] | None = None
        # Enrolled cloned voices: voice_id -> display name.
        self._custom: dict[str, str] = {}
        # Preset synth is torch-free (ONNX), but enrolling a clone runs VieNeu's
        # speaker encoder, which needs torch — so gate cloning on PyTorch.
        self.supports_cloning = _torch_available()

    @staticmethod
    def is_available() -> bool:
        """True if the `vieneu` package is importable (weights load on demand)."""
        return importlib.util.find_spec("vieneu") is not None

    def _get_engine(self):
        # One engine for presets + clones so enrolled voices resolve in infer().
        # CPU -> torch-free ONNX; CUDA -> PyTorch.
        if self._engine is None:
            from vieneu import Vieneu

            if self._device == "cpu":
                self._engine = Vieneu(backend="onnx")  # torch-free, fastest on CPU
            else:
                self._engine = Vieneu(device=self._device)  # CUDA -> PyTorch
        return self._engine

    def _presets(self) -> list[Voice]:
        if self._presets_cache is None:
            engine = self._get_engine()
            voices: list[Voice] = []
            # VieNeu returns (display_label, voice_id) tuples; the id is what
            # infer() expects. Fall back to str() for any non-tuple entry.
            for entry in engine.list_preset_voices():
                if isinstance(entry, (tuple, list)):
                    label, voice_id = str(entry[0]), str(entry[-1])
                else:
                    label = voice_id = str(entry)
                voices.append(Voice(id=voice_id, name=label, model=self.name, language="vi"))
            self._presets_cache = voices
        return self._presets_cache

    def list_voices(self) -> list[Voice]:
        customs = [
            Voice(id=vid, name=name, model=self.name, language="vi")
            for vid, name in self._custom.items()
        ]
        return list(self._presets()) + customs

    def register_voice(
        self,
        voice_id: str,
        name: str,
        sample_path: str,
        *,
        denoise: bool = True,
        use_ref_codes: bool = True,
    ) -> None:
        engine = self._get_engine()  # same engine as presets; cloning needs torch
        with self._lock:
            # Enrol the clone under our id so infer(voice=voice_id) resolves it.
            # denoise/use_ref_codes drive the speaker embedding + reference codes
            # that determine clone fidelity (turn denoise off for clean samples).
            engine.add_voice(
                voice_id, sample_path, denoise=denoise, use_ref_codes=use_ref_codes
            )
        self._custom[voice_id] = name

    def remove_voice(self, voice_id: str) -> bool:
        # VieNeu exposes no un-register; drop it from our advertised set (the
        # in-engine entry is cleared on next restart). True if we held it.
        return self._custom.pop(voice_id, None) is not None

    # Options this backend forwards to VieNeu's infer(). Only `style` is exposed;
    # sampling params are left to VieNeu's internal defaults.
    _INFER_OPTIONS = ("style",)

    def synthesize(
        self, text: str, voice: str, speed: float = 1.0, options: dict | None = None
    ) -> AudioResult:
        options = options or {}
        kwargs = {k: options[k] for k in self._INFER_OPTIONS if k in options}
        # One engine holds both presets and enrolled clones.
        engine = self._get_engine()
        with self._lock:
            audio = engine.infer(text, voice=voice, **kwargs)
        pcm = np.asarray(audio, dtype=np.float32).reshape(-1)
        return AudioResult(pcm=pcm, sample_rate=48000)
