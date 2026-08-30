"""Speech-to-text (ASR): faster-whisper engine + subtitle formatters.

Standalone module, separate from `app/backends/` (TTS). Public surface used by
the transcriptions router.
"""

from __future__ import annotations

from .subtitles import (
    format_timestamp,
    to_json,
    to_srt,
    to_verbose_json,
    to_vtt,
)
from .transcriber import (
    AsrUnavailableError,
    InvalidAudioError,
    Segment,
    TranscriptionResult,
    Word,
    is_available,
    probe_duration,
    transcribe,
)

__all__ = [
    "AsrUnavailableError",
    "InvalidAudioError",
    "Segment",
    "TranscriptionResult",
    "Word",
    "format_timestamp",
    "is_available",
    "probe_duration",
    "to_json",
    "to_srt",
    "to_verbose_json",
    "to_vtt",
    "transcribe",
]
