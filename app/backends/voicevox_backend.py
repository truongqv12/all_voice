"""VOICEVOX adapter (Japanese presets) — https://github.com/VOICEVOX/voicevox_core.

Runs `voicevox_core` in-process (Rust core + onnxruntime), consistent with the
project's torch-free ONNX pattern. Presets only (no cloning), 24 kHz output.

Two RAM-conscious choices for the 1-worker CPU deploy:
- Discovery reads each VVM's *metadata* (cheap) to list speaker×style without
  loading any model for inference.
- Voice models are loaded into the synthesizer lazily — only the VVM holding a
  requested style, on first use — and cached, so startup pulls nothing heavy.

CREDIT: VOICEVOX's terms require crediting the character when publishing audio.
Each voice name here carries `VOICEVOX:<character>` so it shows on GET /v1/voices.

A Docker ENGINE HTTP fallback (POST /audio_query -> /synthesis on :50021) is
documented in the deploy notes; this module implements the in-process core path.
"""

from __future__ import annotations

import importlib.util
import io
import os
import threading

import numpy as np

from .base import AudioResult, Voice, VoiceBackend


def _decode_wav_f32(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode VOICEVOX's WAV bytes to mono float32 PCM + sample rate."""
    import soundfile as sf

    pcm, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)
    if pcm.ndim > 1:  # downmix if ever multi-channel
        pcm = pcm.mean(axis=1)
    return np.asarray(pcm, dtype=np.float32).reshape(-1), int(sr)


class VoicevoxBackend(VoiceBackend):
    name = "voicevox"

    def __init__(self, settings) -> None:
        self._dict_dir = settings.voicevox_dict_dir
        self._vvm_dir = settings.voicevox_vvm_dir
        self._ort_path = settings.voicevox_onnxruntime or ""
        self._allowlist = _parse_allowlist(settings.voicevox_speaker_allowlist)
        self._synth = None
        self._lock = threading.Lock()
        # style_id -> (vvm_path, display_name); built lazily from VVM metadata.
        self._style_to_vvm: dict[int, str] = {}
        self._voices_cache: list[Voice] | None = None
        # VVM paths already loaded into the synthesizer (lazy-load bookkeeping).
        self._loaded: set[str] = set()
        self.supports_cloning = False

    @staticmethod
    def is_available(settings) -> bool:
        """True if `voicevox_core` imports AND the dict dir + >=1 VVM exist AND,
        when an onnxruntime path is configured (the default), that lib is present.

        The wheel bundles no runtime, so a configured-but-missing lib would only
        fail later at synth time; gating registration here keeps a half-installed
        VOICEVOX from advertising voices it cannot render. An empty path opts into
        loading a runtime already on the loader path, so it is not checked here."""
        if importlib.util.find_spec("voicevox_core") is None:
            return False
        if not os.path.isdir(settings.voicevox_dict_dir):
            return False
        ort = settings.voicevox_onnxruntime
        if ort and not os.path.exists(ort):
            return False
        return _has_vvm(settings.voicevox_vvm_dir)

    def _get_synth(self):
        if self._synth is None:
            from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer

            ort = (
                Onnxruntime.load_once(filename=self._ort_path)
                if self._ort_path
                else Onnxruntime.load_once()
            )
            ojt = OpenJtalk(self._dict_dir)
            self._synth = Synthesizer(ort, ojt)
        return self._synth

    def _discover(self) -> None:
        """Populate the style->VVM map + voice list from VVM metadata (no load)."""
        if self._voices_cache is not None:
            return
        from voicevox_core.blocking import VoiceModelFile

        voices: list[Voice] = []
        for vvm_path in sorted(_iter_vvm(self._vvm_dir)):
            with VoiceModelFile.open(vvm_path) as vm:
                for speaker in vm.metas:
                    char = speaker.name
                    uuid = speaker.speaker_uuid
                    for style in speaker.styles:
                        sid = int(style.id)
                        if not _allowed(self._allowlist, uuid, sid):
                            continue
                        self._style_to_vvm[sid] = vvm_path
                        voices.append(
                            Voice(
                                id=str(sid),
                                name=f"{char} · {style.name} · VOICEVOX:{char}",
                                model=self.name,
                                language="ja",
                            )
                        )
        self._voices_cache = voices

    def list_voices(self) -> list[Voice]:
        self._discover()
        return self._voices_cache or []

    def synthesize(
        self, text: str, voice: str, speed: float = 1.0, options: dict | None = None
    ) -> AudioResult:
        self._discover()
        style_id = _parse_style_id(voice)
        vvm_path = self._style_to_vvm.get(style_id)
        if vvm_path is None:
            raise ValueError(f"Unknown VOICEVOX style id: {voice!r}")
        # Build the synthesizer AND load/track VVMs under one lock: `_loaded` is
        # coupled to this single `self._synth`, so a concurrent cold start must
        # not race two Synthesizer instances (one would skip a load it never got).
        # Synthesis is already serialised here, so this costs no concurrency.
        with self._lock:
            synth = self._get_synth()
            if vvm_path not in self._loaded:
                from voicevox_core.blocking import VoiceModelFile

                with VoiceModelFile.open(vvm_path) as vm:
                    synth.load_voice_model(vm)
                self._loaded.add(vvm_path)
            if abs(float(speed) - 1.0) < 1e-6:
                wav = synth.tts(text, style_id)
            else:
                # tts() has no speed knob -> go through an audio query and set
                # speed_scale. Method name differs across core versions.
                make_query = getattr(synth, "create_audio_query", None) or getattr(
                    synth, "audio_query"
                )
                query = make_query(text, style_id)
                query.speed_scale = float(speed)
                wav = synth.synthesis(query, style_id)
        pcm, sr = _decode_wav_f32(wav)
        return AudioResult(pcm=pcm, sample_rate=sr)


def _iter_vvm(vvm_dir: str):
    if not os.path.isdir(vvm_dir):
        return
    for entry in os.scandir(vvm_dir):
        if entry.is_file() and entry.name.endswith(".vvm"):
            yield entry.path


def _has_vvm(vvm_dir: str) -> bool:
    return next(_iter_vvm(vvm_dir), None) is not None


def _parse_style_id(voice: str) -> int:
    # Accept a bare style id ("3") or a "{speaker_uuid}:{style_id}" pair.
    tail = voice.rsplit(":", 1)[-1]
    return int(tail)


def _parse_allowlist(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def _allowed(allowlist: set[str], uuid: str, style_id: int) -> bool:
    if not allowlist:
        return True
    return str(style_id) in allowlist or f"{uuid}:{style_id}" in allowlist
