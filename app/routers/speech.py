"""POST /v1/audio/speech — OpenAI-compatible text-to-speech."""

from __future__ import annotations

import time

import anyio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..audio.effects import apply_speed
from ..audio.encoder import content_type_for, encode
from ..auth import require_api_key
from ..backends.registry import registry
from ..limits import synth_semaphore
from ..logging_config import get_logger
from ..schemas import SpeechRequest

router = APIRouter()
log = get_logger("speech")


@router.post(
    "/audio/speech",
    tags=["speech"],
    summary="Create speech",
    response_class=Response,
    responses={
        200: {
            "description": "Raw audio bytes in the requested `response_format`.",
            "content": {
                "audio/mpeg": {}, "audio/ogg": {}, "audio/aac": {},
                "audio/flac": {}, "audio/wav": {}, "application/octet-stream": {},
            },
        },
        400: {"description": "Invalid request (input too long, bad parameter)."},
        401: {"description": "Missing or invalid API key."},
        404: {"description": "Model not found."},
    },
)
async def create_speech(req: SpeechRequest, _key: str = Depends(require_api_key)) -> Response:
    backend = registry.get(req.model)
    if backend is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Model '{req.model}' not found.", "type": "invalid_request_error", "code": "model_not_found"},
        )

    voice = backend.resolve_voice(req.voice)
    options = req.backend_options()
    start = time.perf_counter()
    # Synthesis + encoding are blocking/CPU-bound -> run off the event loop,
    # bounded by the global semaphore.
    async with synth_semaphore:
        result = await anyio.to_thread.run_sync(
            backend.synthesize, req.input, voice, req.speed, options
        )
    # `speed` is applied gateway-side (pitch-preserving) so it works for every
    # backend, including VieNeu which has no native speed control.
    pcm = await anyio.to_thread.run_sync(apply_speed, result.pcm, req.speed)
    audio = await anyio.to_thread.run_sync(encode, pcm, result.sample_rate, req.response_format)

    elapsed_ms = (time.perf_counter() - start) * 1000
    audio_s = len(pcm) / result.sample_rate if result.sample_rate else 0
    log.info(
        "synth model=%s voice=%s fmt=%s chars=%d speed=%.2f -> %.1fs audio in %.0fms%s",
        backend.name, voice, req.response_format, len(req.input), req.speed,
        audio_s, elapsed_ms, f" opts={options}" if options else "",
    )
    return Response(content=audio, media_type=content_type_for(req.response_format))
