"""faster-whisper wrapper: lazy, config-driven, process-wide singleton model.

Kept separate from `app/backends/` (TTS): one engine, no registry (KISS). The
model loads on the first `transcribe()` call (like VieNeu), then stays cached.
Importing this module never imports faster-whisper — that happens lazily inside
`_get_model()` so the app runs without the `asr` extra and the router can return
a clean 503 via `AsrUnavailableError`.
"""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass, field

from av.error import FFmpegError  # base dep; decode errors surface as this

from ..config import get_settings


class AsrUnavailableError(RuntimeError):
    """Raised when faster-whisper is not installed (the `asr` extra is missing)."""


class InvalidAudioError(ValueError):
    """Raised when the uploaded bytes cannot be decoded as audio (client error)."""


@dataclass
class Word:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class Segment:
    """Mirrors faster-whisper's Segment; enough fields for OpenAI verbose_json."""

    id: int
    seek: int
    start: float
    end: float
    text: str
    temperature: float
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float
    tokens: list[int] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration: float
    segments: list[Segment]
    words: list[Word] | None = None


# Process-wide lazy singleton (the model is heavyweight and stateless); the lock
# stops two concurrent first requests from each loading a copy (transient 2x RAM).
_model = None
_model_lock = threading.Lock()


def is_available() -> bool:
    """True when faster-whisper can be imported (the `asr` extra is installed)."""
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _resolve_device(device: str) -> str:
    """Map the shared `device` setting to a CTranslate2 device.

    Only an explicit `cuda` selects the GPU; `auto`/anything else stays on CPU so
    we don't take a dependency on an external engine just to probe for a GPU.
    """
    return "cuda" if device.strip().lower() == "cuda" else "cpu"


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:  # another thread won the race while we waited
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AsrUnavailableError(
                "ASR engine not installed. Run `uv sync --extra asr`."
            ) from exc
        settings = get_settings()
        _model = WhisperModel(
            settings.asr_model,
            device=_resolve_device(settings.device),
            compute_type=settings.asr_compute_type,
        )
        return _model


def transcribe(
    audio_bytes: bytes,
    *,
    language: str | None = None,
    want_words: bool = False,
    prompt: str | None = None,
    temperature: float = 0.0,
) -> TranscriptionResult:
    """Transcribe audio bytes to text + timing. Blocking/CPU-bound — call off the
    event loop (the router wraps it in `anyio.to_thread` under `synth_semaphore`).

    faster-whisper decodes + resamples to 16kHz mono internally via `av`, so raw
    upload bytes go straight in. `prompt` maps to faster-whisper's `initial_prompt`.
    Undecodable audio (or an invalid `language` code) raises `InvalidAudioError`
    so the router can return a 400 rather than a 500.
    """
    model = _get_model()
    segments: list[Segment] = []
    words: list[Word] | None = [] if want_words else None
    text_parts: list[str] = []
    try:
        # `initial_prompt=None`/`language=None` are the engine defaults; an empty
        # string would be an invalid language code, so normalise it to None.
        segments_gen, info = model.transcribe(
            io.BytesIO(audio_bytes),
            language=language or None,
            word_timestamps=want_words,
            initial_prompt=prompt or None,
            temperature=temperature,
        )
        # The generator is lazy: consume it fully here so all decode I/O stays in
        # this worker thread (never leaks back onto the event loop).
        for s in segments_gen:
            segments.append(
                Segment(
                    id=s.id,
                    seek=s.seek,
                    start=s.start,
                    end=s.end,
                    text=s.text,
                    temperature=s.temperature,
                    avg_logprob=s.avg_logprob,
                    compression_ratio=s.compression_ratio,
                    no_speech_prob=s.no_speech_prob,
                    tokens=list(s.tokens),
                )
            )
            text_parts.append(s.text)
            if want_words and s.words:
                for w in s.words:
                    words.append(  # type: ignore[union-attr]  # non-None when want_words
                        Word(word=w.word, start=w.start, end=w.end, probability=w.probability)
                    )
    except (FFmpegError, ValueError) as exc:
        # Bad container/codec or invalid language code -> client error, not a 500.
        raise InvalidAudioError("Could not decode the audio file.") from exc

    return TranscriptionResult(
        text="".join(text_parts).strip(),
        language=info.language,
        duration=info.duration,
        segments=segments,
        words=words,
    )
