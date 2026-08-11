"""VieNeu-TTS adapter (https://github.com/pnnbao97/VieNeu-TTS).

Engine strategy (VieNeu picks an engine at construction, and cloning is only
available on the PyTorch engine):

- CPU (default): preset synthesis runs on the fast, torch-free ONNX engine.
  Cloned voices need PyTorch, so a second engine is lazily created only when
  cloning is used. This keeps the common preset path fast (priority: perf).
- CUDA/auto: a single PyTorch engine serves everything (fast on GPU).

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
        self._onnx_engine = None
        self._torch_engine = None
        self._lock = threading.Lock()
        self._presets_cache: list[Voice] | None = None
        # Enrolled cloned voices: voice_id -> display name.
        self._custom: dict[str, str] = {}
        # Cloning is only possible when the PyTorch stack is installed.
        self.supports_cloning = _torch_available()

    @staticmethod
    def is_available() -> bool:
        """True if the `vieneu` package is importable (weights load on demand)."""
        return importlib.util.find_spec("vieneu") is not None

    def _onnx(self):
        if self._onnx_engine is None:
            from vieneu import Vieneu

            self._onnx_engine = Vieneu(backend="onnx")  # torch-free, fastest on CPU
        return self._onnx_engine

    def _torch(self):
        if self._torch_engine is None:
            if not _torch_available():
                raise RuntimeError(
                    "Voice cloning requires PyTorch. Install it with `uv sync --extra clone`."
                )
            from vieneu import Vieneu

            self._torch_engine = Vieneu()  # auto: CUDA if present, else CPU PyTorch
        return self._torch_engine

    def _preset_engine(self):
        # GPU: use the PyTorch engine for presets too; CPU: fast ONNX.
        return self._onnx() if self._device == "cpu" else self._torch()

    def _presets(self) -> list[Voice]:
        if self._presets_cache is None:
            engine = self._preset_engine()
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

    def register_voice(self, voice_id: str, name: str, sample_path: str) -> None:
        engine = self._torch()  # cloning requires the PyTorch engine
        with self._lock:
            # Enrol the clone under our id so infer(voice=voice_id) resolves it.
            engine.add_voice(voice_id, sample_path)
        self._custom[voice_id] = name

    def remove_voice(self, voice_id: str) -> None:
        # VieNeu exposes no un-register; drop it from our advertised set (the
        # in-engine entry is cleared on next restart).
        self._custom.pop(voice_id, None)

    # Options this backend forwards to VieNeu's infer().
    _INFER_OPTIONS = (
        "style", "temperature", "top_k", "top_p", "repetition_penalty",
        "silence_p", "crossfade_p", "max_chars",
    )

    def synthesize(
        self, text: str, voice: str, speed: float = 1.0, options: dict | None = None
    ) -> AudioResult:
        options = options or {}
        kwargs = {k: options[k] for k in self._INFER_OPTIONS if k in options}
        # Cloned voices live on the PyTorch engine; presets on the preset engine.
        engine = self._torch() if voice in self._custom else self._preset_engine()
        with self._lock:
            audio = engine.infer(text, voice=voice, **kwargs)
        pcm = np.asarray(audio, dtype=np.float32).reshape(-1)
        return AudioResult(pcm=pcm, sample_rate=48000)
