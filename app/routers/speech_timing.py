"""Supplemental native subtitle timing for VOICEVOX without changing OpenAI speech."""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, HTTPException

from ..backends.registry import registry
from ..client_identity import Identity, Tier, resolve_tier
from ..config import Settings, get_settings
from ..limits import admit
from ..quota import quota
from ..schemas import SpeechTimingRequest, SpeechTimingResponse, SubtitleTimingCue

router = APIRouter()


@router.post("/audio/speech/timing", response_model=SpeechTimingResponse, tags=["speech"])
async def create_speech_timing(
    req: SpeechTimingRequest,
    ident: Identity = Depends(resolve_tier),
    settings: Settings = Depends(get_settings),
) -> SpeechTimingResponse:
    backend, explicit = registry.resolve(req.model)
    if backend is None or backend.name != "voicevox" or not explicit:
        raise HTTPException(status_code=400, detail={"message": "Native subtitle timing is available only for VOICEVOX.", "type": "invalid_request_error", "code": "timing_not_supported"})
    voice = backend.resolve_voice(req.voice, strict=True)
    if voice is None:
        raise HTTPException(status_code=404, detail={"message": f"Voice '{req.voice}' was not found.", "type": "invalid_request_error", "code": "unknown_voice"})
    if ident.tier is Tier.ANON:
        # Bound per-request analysis cost to the same ceiling as streaming synth so a
        # single call cannot run OpenJTalk over an unbounded input on the shared worker.
        if len(req.input) > settings.anon_max_chars_stream:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Input exceeds the {settings.anon_max_chars_stream}-character limit.",
                    "type": "invalid_request_error", "code": "input_too_long",
                },
            )
        quota.allow_rate(ident.ip, settings)
    try:
        async with admit(ident.ip, settings):
            chunk_max_chars = settings.stream_max_chunk_chars if req.streaming else None
            cues = await anyio.to_thread.run_sync(
                backend.subtitle_timing, req.input, voice, req.speed, chunk_max_chars
            )
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc), "type": "server_error", "code": "timing_unavailable"}) from exc
    return SpeechTimingResponse(cues=[SubtitleTimingCue(start=cue.start, end=cue.end, text=cue.text) for cue in cues])
