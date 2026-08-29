"""POST /v1/audio/speech — OpenAI-compatible text-to-speech."""

from __future__ import annotations

import time

import anyio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..audio.encoder import content_type_for, encode
from ..auth import require_api_key
from ..backends.base import InvalidOption
from ..backends.registry import registry
from ..limits import synth_semaphore
from ..logging_config import get_logger
from ..schemas import SpeechRequest

router = APIRouter()
log = get_logger("speech")

_BINARY_AUDIO_RESPONSE = {"schema": {"type": "string", "format": "binary"}}


@router.post(
    "/audio/speech",
    tags=["speech"],
    summary="Tạo giọng nói",
    response_class=Response,
    responses={
        200: {
            "description": "Bytes audio thô theo `response_format` yêu cầu.",
            "content": {
                "audio/mpeg": _BINARY_AUDIO_RESPONSE,
                "audio/ogg": _BINARY_AUDIO_RESPONSE,
                "audio/aac": _BINARY_AUDIO_RESPONSE,
                "audio/flac": _BINARY_AUDIO_RESPONSE,
                "audio/wav": _BINARY_AUDIO_RESPONSE,
                "audio/pcm": _BINARY_AUDIO_RESPONSE,
            },
        },
        400: {"description": "Yêu cầu không hợp lệ (input quá dài, tham số sai)."},
        401: {"description": "Thiếu hoặc sai API key."},
        404: {"description": "Không tìm thấy model."},
    },
)
async def create_speech(req: SpeechRequest, _key: str = Depends(require_api_key)) -> Response:
    backend, explicit = registry.resolve(req.model)
    if backend is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Model '{req.model}' not found.", "type": "invalid_request_error", "code": "model_not_found"},
        )

    # Explicit model + unknown voice -> 404 (don't silently read the wrong voice
    # in the wrong language). An OpenAI-generic model stays lenient.
    voice = backend.resolve_voice(req.voice, strict=explicit)
    if voice is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Voice '{req.voice}' not found for model '{req.model}'.", "type": "invalid_request_error", "code": "unknown_voice"},
        )
    options = req.backend_options()
    start = time.perf_counter()
    # Synthesis + encoding are blocking/CPU-bound -> run off the event loop,
    # bounded by the global semaphore.
    async with synth_semaphore:
        try:
            result = await anyio.to_thread.run_sync(
                backend.synthesize, req.input, voice, req.speed, options
            )
        except InvalidOption as exc:
            # A backend rejected a tuning knob (e.g. an unknown `style`) -> 400,
            # not the 500 an unexpected error would get.
            raise HTTPException(
                status_code=400,
                detail={"message": str(exc), "type": "invalid_request_error", "code": "invalid_option"},
            )
    # `speed` is forwarded to the backend; a backend honours it only if it has
    # native speed control. VieNeu does not, so speed is a no-op there — the
    # gateway no longer time-stretches (that hurt speech quality).
    pcm = result.pcm
    audio = await anyio.to_thread.run_sync(encode, pcm, result.sample_rate, req.response_format)

    elapsed_ms = (time.perf_counter() - start) * 1000
    audio_s = len(pcm) / result.sample_rate if result.sample_rate else 0
    log.info(
        "synth model=%s voice=%s fmt=%s chars=%d speed=%.2f -> %.1fs audio in %.0fms%s",
        backend.name, voice, req.response_format, len(req.input), req.speed,
        audio_s, elapsed_ms, f" opts={options}" if options else "",
    )
    return Response(content=audio, media_type=content_type_for(req.response_format))
