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
import json
import logging
import os
import threading

import numpy as np

logger = logging.getLogger(__name__)

from .base import AudioResult, InvalidOption, SubtitleTimingCue, Voice, VoiceBackend
from ..streaming import sentence_split


def _decode_wav_f32(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode VOICEVOX's WAV bytes to mono float32 PCM + sample rate."""
    import soundfile as sf

    pcm, sr = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=False)
    if pcm.ndim > 1:  # downmix if ever multi-channel
        pcm = pcm.mean(axis=1)
    return np.asarray(pcm, dtype=np.float32).reshape(-1), int(sr)


# VOICEVOX AudioQuery prosody knobs, read from the request `extra` bag by name.
# Speed has its own top-level `speed` param; these cover the rest of the query.
# `pause_length_scale` (間 — the gap between phrases/sentences) is the strongest
# lever for an elderly audience that needs time to follow; `intonation_scale`
# (抑揚) calms an otherwise brisk announcer read. Each is applied only if the
# running voicevox_core exposes that attribute, so an older core silently
# ignores a knob it lacks instead of raising.
_QUERY_TUNING_KEYS = (
    "pause_length_scale",
    "intonation_scale",
    "pitch_scale",
    "volume_scale",
)


def _tuning_from_options(options: dict | None) -> dict[str, float]:
    """Positive-float VOICEVOX query knobs pulled from the request options.

    Raises InvalidOption (→ HTTP 400) on a non-numeric or non-positive value so a
    typo fails loudly instead of rendering at an unintended setting."""
    if not options:
        return {}
    tuning: dict[str, float] = {}
    for key in _QUERY_TUNING_KEYS:
        raw = options.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise InvalidOption(f"VOICEVOX option {key!r} must be a number, got {raw!r}")
        if value <= 0:
            raise InvalidOption(f"VOICEVOX option {key!r} must be > 0, got {value}")
        tuning[key] = value
    return tuning


def _apply_query_tuning(query, tuning: dict[str, float]) -> None:
    """Set each requested knob on the AudioQuery, skipping any the core lacks."""
    for key, value in tuning.items():
        if hasattr(query, key):
            setattr(query, key, value)


def _apply_user_dict(ojt, path: str) -> None:
    """Load persistent reading overrides from a JSON file into the OpenJtalk dict.

    Fixes OpenJTalk 誤読 (e.g. ピンク筋 read as ピンクスジ instead of ピンクキン) on rare
    compounds it mis-guesses. Best-effort: a missing path/file, a core without
    UserDict, or one bad entry never fails synthesis — it just falls back to
    OpenJTalk's own reading. Schema per word: surface, pronunciation (katakana),
    accent_type (int, 0=heiban), word_type (default COMMON_NOUN), priority (0-10)."""
    if not path or not os.path.exists(path):
        return
    try:
        from voicevox_core import UserDictWord
        from voicevox_core.blocking import UserDict
    except Exception as exc:  # a core build without UserDict
        logger.warning("VOICEVOX user dict skipped (UserDict unavailable): %s", exc)
        return
    try:
        with open(path, encoding="utf-8") as fh:
            words = json.load(fh).get("words", [])
    except (OSError, ValueError) as exc:
        logger.warning("VOICEVOX user dict %s unreadable: %s", path, exc)
        return
    user_dict = UserDict()
    added = 0
    for entry in words:
        surface = entry.get("surface")
        pronunciation = entry.get("pronunciation")
        if not surface or not pronunciation:
            continue
        try:
            user_dict.add_word(
                UserDictWord(
                    surface,
                    pronunciation,
                    int(entry.get("accent_type", 0)),
                    entry.get("word_type", "COMMON_NOUN"),
                    int(entry.get("priority", 5)),
                )
            )
            added += 1
        except Exception as exc:  # a single malformed entry must not drop the rest
            logger.warning("VOICEVOX user dict word %r skipped: %s", surface, exc)
    if added:
        ojt.use_user_dict(user_dict)
        logger.info("VOICEVOX user dict: %d reading override(s) from %s", added, path)


class VoicevoxBackend(VoiceBackend):
    name = "voicevox"

    def __init__(self, settings) -> None:
        self._dict_dir = settings.voicevox_dict_dir
        self._vvm_dir = settings.voicevox_vvm_dir
        self._ort_path = settings.voicevox_onnxruntime or ""
        self._user_dict_path = getattr(settings, "voicevox_user_dict", "") or ""
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
            _apply_user_dict(ojt, self._user_dict_path)
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
        tuning = _tuning_from_options(options)
        with self._lock:
            synth = self._load_voice_model(vvm_path)
            if abs(float(speed) - 1.0) < 1e-6 and not tuning:
                wav = synth.tts(text, style_id)
            else:
                # tts() exposes no prosody knobs -> go through an audio query when
                # speed differs from 1.0 OR any query tuning was requested, and set
                # the fields. Method name differs across core versions.
                make_query = getattr(synth, "create_audio_query", None) or getattr(
                    synth, "audio_query"
                )
                query = make_query(text, style_id)
                query.speed_scale = float(speed)
                _apply_query_tuning(query, tuning)
                wav = synth.synthesis(query, style_id)
        pcm, sr = _decode_wav_f32(wav)
        return AudioResult(pcm=pcm, sample_rate=sr)

    def subtitle_timing(
        self, text: str, voice: str, speed: float = 1.0, chunk_max_chars: int | None = None
    ) -> list[SubtitleTimingCue]:
        """Build queries matching buffered or sentence-streamed VOICEVOX audio."""
        self._discover()
        style_id = _parse_style_id(voice)
        vvm_path = self._style_to_vvm.get(style_id)
        if vvm_path is None:
            raise ValueError(f"Unknown VOICEVOX style id: {voice!r}")
        with self._lock:
            synth = self._load_voice_model(vvm_path)
            make_query = getattr(synth, "create_audio_query", None) or getattr(synth, "audio_query")
            chunks = sentence_split(text, chunk_max_chars) if chunk_max_chars else [text]
            cues: list[SubtitleTimingCue] = []
            offset = 0.0
            for chunk in chunks:
                query = make_query(chunk, style_id)
                query.speed_scale = float(speed)
                chunk_cues = _accent_phrases_to_cues(query)
                cues.extend(
                    SubtitleTimingCue(start=cue.start + offset, end=cue.end + offset, text=cue.text)
                    for cue in chunk_cues
                )
                if chunk_cues:
                    offset = chunk_cues[-1].end + offset
        return cues

    def _load_voice_model(self, vvm_path: str):
        """Load a VVM once while the backend synthesis lock is held."""
        synth = self._get_synth()
        if vvm_path not in self._loaded:
            from voicevox_core.blocking import VoiceModelFile

            with VoiceModelFile.open(vvm_path) as vm:
                synth.load_voice_model(vm)
            self._loaded.add(vvm_path)
        return synth


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


def _field(value, name: str, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _mora_seconds(mora) -> float:
    consonant = _field(mora, "consonant_length") or 0.0
    vowel = _field(mora, "vowel_length") or 0.0
    return float(consonant) + float(vowel)


def _accent_phrases_to_cues(query) -> list[SubtitleTimingCue]:
    """Convert VOICEVOX AudioQuery moras into one caption per accent phrase."""
    speed = max(float(_field(query, "speed_scale", 1.0)), 0.01)
    cursor = float(_field(query, "pre_phoneme_length", 0.0)) / speed
    cues: list[SubtitleTimingCue] = []
    for phrase in _field(query, "accent_phrases", []):
        moras = _field(phrase, "moras", [])
        text = "".join(str(_field(mora, "text", "")) for mora in moras).strip()
        duration = sum(_mora_seconds(mora) for mora in moras)
        duration += _mora_seconds(_field(phrase, "pause_mora")) if _field(phrase, "pause_mora") is not None else 0.0
        end = cursor + duration / speed
        if text and end > cursor:
            cues.append(SubtitleTimingCue(start=cursor, end=end, text=text))
        cursor = end
    # VOICEVOX appends this tail after the final accent phrase. It does not form
    # caption text, but the final cue must span the generated audio duration.
    if cues:
        last = cues[-1]
        cues[-1] = SubtitleTimingCue(
            start=last.start,
            end=last.end + float(_field(query, "post_phoneme_length", 0.0)) / speed,
            text=last.text,
        )
    return cues


def _parse_allowlist(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


def _allowed(allowlist: set[str], uuid: str, style_id: int) -> bool:
    if not allowlist:
        return True
    return str(style_id) in allowlist or f"{uuid}:{style_id}" in allowlist
