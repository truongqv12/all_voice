"""Pure formatters: transcription result -> SRT / VTT / OpenAI JSON shapes.

No faster-whisper import here — these are deterministic string/dict builders over
the dataclasses in `transcriber`, so they test fast without loading a model.
They rely only on duck-typed attributes (`.start`, `.end`, `.text`, ...), so a
list of hand-built segments works in tests just like real engine output.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # hints only; avoids importing the engine module at runtime
    from .transcriber import Segment, TranscriptionResult


def format_timestamp(seconds: float, *, sep: str = ",") -> str:
    """`HH:MM:SS{sep}mmm` — `sep=','` for SRT, `sep='.'` for VTT."""
    if seconds < 0:
        seconds = 0.0
    ms = round(seconds * 1000.0)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(segments: Iterable[Segment]) -> str:
    """SubRip: numbered cues, `,` millisecond separator."""
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(
            f"{format_timestamp(seg.start, sep=',')} --> {format_timestamp(seg.end, sep=',')}"
        )
        lines.append(seg.text.strip())
        lines.append("")  # blank line separates cues
    return "\n".join(lines)


def to_vtt(segments: Iterable[Segment]) -> str:
    """WebVTT: `WEBVTT` header, `.` millisecond separator."""
    lines: list[str] = ["WEBVTT", ""]
    for seg in segments:
        lines.append(
            f"{format_timestamp(seg.start, sep='.')} --> {format_timestamp(seg.end, sep='.')}"
        )
        lines.append(seg.text.strip())
        lines.append("")
    return "\n".join(lines)


def to_verbose_json(result: TranscriptionResult) -> dict:
    """OpenAI `verbose_json` shape; top-level `words` only when present."""
    out: dict = {
        "task": "transcribe",
        "language": result.language,
        "duration": result.duration,
        "text": result.text,
        "segments": [
            {
                "id": s.id,
                "seek": s.seek,
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "tokens": s.tokens,
                "temperature": s.temperature,
                "avg_logprob": s.avg_logprob,
                "compression_ratio": s.compression_ratio,
                "no_speech_prob": s.no_speech_prob,
            }
            for s in result.segments
        ],
    }
    if result.words is not None:
        out["words"] = [
            {"word": w.word, "start": w.start, "end": w.end} for w in result.words
        ]
    return out


def to_json(result: TranscriptionResult) -> dict:
    """OpenAI default `json` shape: just the text."""
    return {"text": result.text}
