"""GET /v1/voices — voices merged across all registered backends.

Custom extension (not part of the OpenAI spec) for voice discovery."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import require_api_key
from ..backends.registry import registry
from ..schemas import VoiceInfo, VoiceList

router = APIRouter()


@router.get("/voices", response_model=VoiceList, tags=["voices"], summary="List all voices (preset + cloned)")
async def list_voices(
    model: str | None = Query(None, description="Only voices of this backend (e.g. `vieneu`)."),
    language: str | None = Query(None, description="Only voices in this language (e.g. `vi`, `ja`, `en`)."),
    _key: str = Depends(require_api_key),
) -> VoiceList:
    # Additive filters: no params -> every voice, as before. An unmatched filter
    # returns an empty list (discovery-friendly), not an error.
    voices = registry.all_voices()
    if model:
        voices = [v for v in voices if v.model == model]
    if language:
        voices = [v for v in voices if v.language == language]
    data = [
        VoiceInfo(id=v.id, name=v.name, model=v.model, language=v.language, styles=v.styles)
        for v in voices
    ]
    return VoiceList(data=data)
