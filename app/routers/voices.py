"""GET /v1/voices — voices merged across all registered backends, plus per-voice
audio previews ("nghe thử").

Custom extension (not part of the OpenAI spec) for voice discovery."""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .. import previews
from ..auth import require_api_key
from ..backends.registry import registry
from ..config import get_settings
from ..schemas import VoiceInfo, VoiceList
from ..voice_store import voice_store

router = APIRouter()


@router.get("/voices", response_model=VoiceList, tags=["voices"], summary="Liệt kê tất cả giọng (preset + clone)")
async def list_voices(
    model: str | None = Query(None, description="Chỉ giọng của backend này (vd `vieneu`, `kokoro`, `voicevox`)."),
    language: str | None = Query(None, description="Chỉ giọng theo ngôn ngữ này (vd `vi`, `en`, `ja`)."),
    preview: str | None = Query(None, description="`base64` để nhúng mp3 (chỉ preview đã cache)."),
    _key: str = Depends(require_api_key),
) -> VoiceList:
    # Additive filters: no params -> every voice, as before. An unmatched filter
    # returns an empty list (discovery-friendly), not an error.
    voices = registry.all_voices()
    if model:
        voices = [v for v in voices if v.model == model]
    if language:
        voices = [v for v in voices if v.language == language]
    # `preview_b64_if_current` NEVER synthesizes -> base64 reflects the warmed
    # cache only (null for not-yet-warmed voices); the list call triggers no synth.
    want_b64 = preview == "base64"
    data = [
        VoiceInfo(
            id=v.id, name=v.name, model=v.model, language=v.language, styles=v.styles,
            preview_url=previews.preview_url_for(v.model, v.id),
            preview_base64=(previews.preview_b64_if_current(v.model, v.id) if want_b64 else None),
        )
        for v in voices
    ]
    return VoiceList(data=data)


def _bearer_ok(request: Request) -> bool:
    h = request.headers.get("authorization", "")
    token = h[7:].strip() if h[:7].lower() == "bearer " else ""
    return token in get_settings().api_key_set


@router.get(
    "/voices/{model}/{voice_id}/preview",
    tags=["voices"],
    summary="Nghe thử giọng (preset: công khai; clone: cần key)",
)
async def voice_preview(model: str, voice_id: str, request: Request) -> FileResponse:
    # Split auth: preset previews are public (a browser <audio src> plays them
    # with no header); a clone preview renders a real person's cloned timbre
    # (biometric), so it requires a valid Bearer key. Fail closed on the union of
    # the live store AND the cached artifact's sidecar flag, so a store/backend
    # divergence (multi-worker post-delete, an orphan) can never serve a clone
    # preview publicly.
    is_clone = voice_store.get(voice_id) is not None or previews.sidecar_marks_clone(model, voice_id)
    if is_clone and not _bearer_ok(request):
        raise HTTPException(status_code=401, detail={
            "message": "API key required to preview a cloned voice.",
            "type": "invalid_request_error", "code": "invalid_api_key"})
    # Staleness via is_current (sidecar text_hash), not bare exists(): a passage
    # change never serves stale bytes. Generation is bounded inside ensure_preview
    # (_GEN_SEM), so this route never holds a synth_semaphore permit.
    path = previews.preview_path(model, voice_id)
    if not previews.is_current(path):
        made = await anyio.to_thread.run_sync(previews.ensure_preview, model, voice_id)
        if made is None:
            raise HTTPException(status_code=404, detail={
                "message": f"No preview for voice '{voice_id}' on model '{model}'.",
                "type": "invalid_request_error", "code": "preview_not_found"})
        path = made
    cache = "private, no-store" if is_clone else "public, max-age=86400"
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": cache})
