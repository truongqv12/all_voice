"""POST /v1/audio/speech — OpenAI-compatible text-to-speech.

Anonymous-capable: no key = ANON tier (rate + daily character budget + admission
queue), a valid key = TRUSTED (no per-request limits). Cost is billed in characters
up front and refunded on any path that doesn't deliver audio (#4)."""

from __future__ import annotations

import time

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .. import result_cache
from ..audio.encoder import content_type_for, encode
from ..backends.base import InvalidOption
from ..backends.registry import registry
from ..client_identity import Identity, Tier, resolve_tier
from ..config import Settings, get_settings
from ..limits import admit
from ..logging_config import get_logger
from ..quota import quota
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
        400: {"description": "Yêu cầu không hợp lệ (input quá dài cho tầng anon, tham số sai)."},
        401: {"description": "Anon bị tắt và không có key hợp lệ."},
        404: {"description": "Không tìm thấy model."},
        429: {"description": "Vượt rate-limit / budget ngày, hoặc server quá tải."},
    },
)
async def create_speech(
    req: SpeechRequest,
    request: Request,
    ident: Identity = Depends(resolve_tier),
    settings: Settings = Depends(get_settings),
) -> Response:
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

    anon = ident.tier is Tier.ANON
    # ANON callers are capped so one buffered synth stays under Cloudflare's ~100s
    # edge timeout; long input goes to /v1/audio/stream instead.
    if anon and len(req.input) > settings.anon_max_chars_buffered:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    f"Input exceeds the {settings.anon_max_chars_buffered}-character limit for "
                    "buffered speech. Use POST /v1/audio/stream for long text."
                ),
                "type": "invalid_request_error", "code": "input_too_long",
            },
        )

    options = req.backend_options()
    reserved = 0
    committed = False
    if anon:
        quota.allow_rate(ident.ip, settings)  # RateLimited -> 429 (before reserving anything)
        await anyio.to_thread.run_sync(quota.reserve_chars, ident.ip, len(req.input), settings)
        reserved = len(req.input)

    start = time.perf_counter()
    try:
        cache_key = result_cache.key(
            backend.name, voice, req.input, req.speed, req.response_format, options
        )
        cached = result_cache.get(cache_key)
        if cached is not None:
            committed = True  # a cache hit still delivers audio -> keep the budget
            log.info(
                "synth model=%s voice=%s fmt=%s chars=%d cache=hit -> %d bytes",
                backend.name, voice, req.response_format, len(req.input), len(cached),
            )
            return Response(content=cached, media_type=content_type_for(req.response_format))

        # Synthesis + encoding are blocking/CPU-bound -> off the event loop, under
        # the admission gate (per-IP concurrency + bounded queue + slot timeout).
        async with admit(ident.ip, settings):
            try:
                result = await anyio.to_thread.run_sync(
                    backend.synthesize, req.input, voice, req.speed, options
                )
            except InvalidOption as exc:
                # A backend rejected a tuning knob (e.g. an unknown `style`) -> 400.
                raise HTTPException(
                    status_code=400,
                    detail={"message": str(exc), "type": "invalid_request_error", "code": "invalid_option"},
                )
        # `speed` is forwarded to the backend; a backend honours it only if it has
        # native speed control. VieNeu does not, so speed is a no-op there.
        pcm = result.pcm
        audio = await anyio.to_thread.run_sync(encode, pcm, result.sample_rate, req.response_format)
        result_cache.put(cache_key, audio)
        committed = True

        elapsed_ms = (time.perf_counter() - start) * 1000
        audio_s = len(pcm) / result.sample_rate if result.sample_rate else 0
        log.info(
            "synth model=%s voice=%s fmt=%s chars=%d speed=%.2f ip=%s tier=%s cache=miss -> %.1fs audio in %.0fms%s",
            backend.name, voice, req.response_format, len(req.input), req.speed,
            ident.ip, ident.tier.value, audio_s, elapsed_ms, f" opts={options}" if options else "",
        )
        return Response(content=audio, media_type=content_type_for(req.response_format))
    finally:
        # Refund the reserved characters on every path that did NOT return audio
        # (overload/timeout/400/backend error) so a rejected request is net-zero.
        if reserved and not committed:
            await anyio.to_thread.run_sync(quota.refund_chars, ident.ip, reserved)
