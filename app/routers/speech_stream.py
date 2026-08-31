"""POST /v1/audio/stream — long-read streaming TTS (all-voice extension).

Not part of the OpenAI spec and separate from `/v1/audio/speech`: it takes long
text, splits it into sentences, and streams one continuous MP3 as each sentence is
synthesized. This is how long reads dodge Cloudflare's ~100s edge timeout (bytes
flow the whole time) while RAM stays flat (one sentence in flight, never the whole
file buffered).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..backends.registry import registry
from ..client_identity import Identity, Tier, resolve_tier
from ..config import Settings, get_settings
from ..limits import close_stream, open_stream
from ..quota import quota
from ..schemas import StreamSpeechRequest
from ..streaming import sentence_split, synth_stream

router = APIRouter()


@router.post(
    "/audio/stream",
    tags=["speech"],
    summary="Đọc văn bản dài (stream mp3)",
    response_class=StreamingResponse,
    responses={
        200: {"description": "Stream `audio/mpeg` liên tục.", "content": {"audio/mpeg": {"schema": {"type": "string", "format": "binary"}}}},
        400: {"description": "Văn bản vượt trần tầng anon, hoặc tham số sai."},
        401: {"description": "Anon bị tắt và không có key hợp lệ."},
        404: {"description": "Không tìm thấy model/voice."},
        429: {"description": "Vượt rate-limit, quá nhiều stream mở, hoặc server quá tải."},
    },
)
async def create_stream(
    req: StreamSpeechRequest,
    request: Request,
    ident: Identity = Depends(resolve_tier),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    backend, explicit = registry.resolve(req.model)
    if backend is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Model '{req.model}' not found.", "type": "invalid_request_error", "code": "model_not_found"},
        )
    voice = backend.resolve_voice(req.voice, strict=explicit)
    if voice is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"Voice '{req.voice}' not found for model '{req.model}'.", "type": "invalid_request_error", "code": "unknown_voice"},
        )

    anon = ident.tier is Tier.ANON
    if anon and len(req.input) > settings.anon_max_chars_stream:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Input exceeds the {settings.anon_max_chars_stream}-character streaming limit.",
                "type": "invalid_request_error", "code": "input_too_long",
            },
        )
    if anon:
        quota.allow_rate(ident.ip, settings)  # RateLimited -> 429

    # Reserve one stream slot for the whole connection (#8); over the per-IP cap ->
    # Overloaded (429) BEFORE the response starts. Released when the body finishes.
    open_stream(ident.ip, settings)
    chunks = sentence_split(req.input, settings.stream_max_chunk_chars)
    options = req.backend_options()

    async def body():
        try:
            async for data in synth_stream(
                backend=backend, voice=voice, chunks=chunks,
                ident=ident, request=request, speed=req.speed, options=options, settings=settings,
            ):
                yield data
        finally:
            close_stream(ident.ip)

    return StreamingResponse(
        body(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
