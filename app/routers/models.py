"""GET /v1/models — registered backends, in OpenAI's model-list shape."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_api_key
from ..backends.registry import registry
from ..schemas import ModelInfo, ModelList

router = APIRouter()

# Fixed creation timestamp (avoids nondeterministic responses).
_CREATED = 1723334400


@router.get("/models", response_model=ModelList, tags=["models"], summary="List backends")
async def list_models(_key: str = Depends(require_api_key)) -> ModelList:
    data = [ModelInfo(id=name, created=_CREATED) for name in registry.models()]
    return ModelList(data=data)
