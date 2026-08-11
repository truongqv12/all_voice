"""GET /v1/voices — voices merged across all registered backends.

Custom extension (not part of the OpenAI spec) for voice discovery."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..backends.registry import registry
from ..schemas import VoiceInfo, VoiceList

router = APIRouter()


@router.get("/voices", response_model=VoiceList, tags=["voices"], summary="List all voices (preset + cloned)")
async def list_voices(_key: str = Depends(require_api_key)) -> VoiceList:
    data = [
        VoiceInfo(id=v.id, name=v.name, model=v.model, language=v.language, styles=v.styles)
        for v in registry.all_voices()
    ]
    return VoiceList(data=data)
