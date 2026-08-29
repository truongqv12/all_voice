"""POST /v1/audio/transcriptions — OpenAI-compatible speech-to-text.

Thin router over `app/asr`: multipart in, transcript out in the requested
`response_format` (json/text/srt/vtt/verbose_json). Reuses the shared auth,
CPU-budget semaphore, and OpenAI error envelope; never touches the TTS core.
"""

from __future__ import annotations

import time
from functools import partial

import anyio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from ..asr import (
    AsrUnavailableError,
    InvalidAudioError,
    to_json,
    to_srt,
    to_verbose_json,
    to_vtt,
    transcribe,
)
from ..auth import require_api_key
from ..limits import synth_semaphore
from ..logging_config import get_logger
from ..schemas import TranscriptionResponseFormat, TranscriptionVerbose

router = APIRouter()
log = get_logger("transcribe")

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # OpenAI limit: 25 MiB
_PLAIN = "text/plain; charset=utf-8"


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"message": message, "type": "invalid_request_error", "code": code},
    )


@router.post(
    "/audio/transcriptions",
    tags=["transcriptions"],
    summary="Create transcription",
    responses={
        200: {
            "model": TranscriptionVerbose,
            "description": (
                "Transcript in the requested `response_format`: `json` -> `{\"text\": ...}`; "
                "`verbose_json` -> full segment/word timing (schema shown); "
                "`text`/`srt`/`vtt` -> plain text."
            ),
        },
        400: {"description": "Invalid request (empty/undecodable file, too large, bad parameter)."},
        401: {"description": "Missing or invalid API key."},
        503: {"description": "ASR engine not installed (`uv sync --extra asr`)."},
    },
)
async def create_transcription(
    file: UploadFile = File(..., description="Audio file to transcribe."),
    # Accepted for OpenAI compatibility; a single configured engine answers every
    # model name (logged, not routed).
    model: str = Form("whisper-1"),
    language: str | None = Form(None, description="ISO-639-1 hint (e.g. `vi`); auto-detected if omitted."),
    response_format: TranscriptionResponseFormat = Form("json"),
    prompt: str | None = Form(None, description="Optional text to bias decoding (maps to initial_prompt)."),
    temperature: float = Form(0.0, ge=0.0, le=1.0),
    # OpenAI sends the key with brackets; accept the bare key too for safety.
    timestamp_granularities: list[str] = Form([], alias="timestamp_granularities[]"),
    timestamp_granularities_bare: list[str] = Form([], alias="timestamp_granularities"),
    _key: str = Depends(require_api_key),
) -> Response:
    data = await file.read()
    if not data:
        raise _error(400, "file is empty.", "invalid_audio_file")
    if len(data) > MAX_AUDIO_BYTES:
        raise _error(400, "file exceeds the 25 MiB limit.", "audio_file_too_large")

    granularities = [*timestamp_granularities, *timestamp_granularities_bare]
    want_words = "word" in granularities

    start = time.perf_counter()
    # Transcription is blocking/CPU-bound -> off the event loop, bounded by the
    # shared CPU-budget semaphore (same MAX_CONCURRENCY as TTS synthesis).
    try:
        async with synth_semaphore:
            result = await anyio.to_thread.run_sync(
                partial(
                    transcribe,
                    data,
                    language=language,
                    want_words=want_words,
                    prompt=prompt,
                    temperature=temperature,
                )
            )
    except AsrUnavailableError:
        raise _error(
            503, "ASR engine not installed. Run `uv sync --extra asr`.", "asr_unavailable"
        )
    except InvalidAudioError:
        raise _error(
            400, "Could not decode the audio file. Provide a valid audio file.", "invalid_audio_file"
        )

    if response_format == "text":
        payload: Response = Response(result.text, media_type=_PLAIN)
    elif response_format == "srt":
        payload = Response(to_srt(result.segments), media_type=_PLAIN)
    elif response_format == "vtt":
        payload = Response(to_vtt(result.segments), media_type=_PLAIN)
    elif response_format == "verbose_json":
        payload = JSONResponse(to_verbose_json(result))
    else:  # "json" (default)
        payload = JSONResponse(to_json(result))

    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "transcribe model=%s bytes=%d fmt=%s lang=%s words=%s -> %d segments %.1fs audio in %.0fms",
        model, len(data), response_format, result.language, want_words,
        len(result.segments), result.duration, elapsed_ms,
    )
    return payload
