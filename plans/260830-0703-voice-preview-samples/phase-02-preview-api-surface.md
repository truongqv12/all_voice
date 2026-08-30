---
title: "Phase 2: Preview API surface"
status: done
---

# Phase 2: Preview API surface

## Overview

Expose the engine over HTTP: add `preview_url` (always) and optional
`preview_base64` to `GET /v1/voices`, and add the preview endpoint
`GET /v1/voices/{model}/{voice_id}/preview` with a **split auth posture**:
**preset previews are public** (browser `<audio>` plays them), **clone previews
require a valid API key** (they render a real person's cloned timbre).

> **Red-team revisions (applied):** (a) preset previews public, clone previews
> keyed (fixes cloned-voice timbre exposure + the unauth existence oracle for
> clones); (b) clone responses use `Cache-Control: private, no-store`; (c) the
> hot path uses `is_current()` (sidecar `text_hash`), not bare `path.exists()`, so
> a passage change never serves stale bytes; (d) `?preview=base64` inlines only
> already-fresh previews (no full-catalog inline synth); (e) the route does NOT
> hold a `synth_semaphore` permit — generation is bounded inside `ensure_preview`.

## Requirements

- [ ] `VoiceInfo` carries `preview_url: str` and `preview_base64: str | None = None`.
- [ ] `GET /v1/voices` sets `preview_url` for every voice; `?preview=base64` fills `preview_base64` **only for currently-cached previews** (null otherwise).
- [ ] `GET /v1/voices/{model}/{voice_id}/preview`: preset → public; clone (`voice_store.get(voice_id) is not None`) → requires a valid Bearer key or 401.
- [ ] Response is mp3 `audio/mpeg`; preset `Cache-Control: public, max-age=86400`; clone `Cache-Control: private, no-store`.
- [ ] Hot path serves a fresh cache directly; miss/stale generates via `ensure_preview` (bounded by `preview_concurrency`, off the paid semaphore). Unknown model/voice → 404 with no synthesis.

## Architecture

Both live in `app/routers/voices.py`. The preview route takes **no auth
dependency** — instead it branches: a clone id (present in `voice_store`) demands
a valid key checked manually against `settings.api_key_set` (auth.py:64-66),
returning 401 on miss; a preset serves publicly. This keeps one URL while giving
clones real protection. URL building percent-encodes ids (spaces like "Trúc Ly",
VOICEVOX `uuid:style`); FastAPI decodes path params. `FileResponse` streams the
cached file.

## Related Code Files

- Modify: `app/schemas.py` (`VoiceInfo` fields)
- Modify: `app/routers/voices.py` (list `preview` param + fields; new preview route)

## Implementation Steps

1. **Schema** — extend `VoiceInfo` in `app/schemas.py`:
   ```python
   preview_url: str = Field(description="Đường dẫn nghe thử (mp3). Preset: không cần key; clone: cần Bearer key.")
   preview_base64: str | None = Field(
       default=None, description="mp3 base64 — chỉ có khi ?preview=base64 và preview đã được tạo sẵn.")
   ```
   (Keep existing `id/name/model/language/styles`.)

2. **List endpoint** — add `preview: str | None = Query(None, description="`base64` để nhúng mp3 (chỉ preview đã cache).")`:
   ```python
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
   ```
   `preview_b64_if_current` never synthesizes → base64 reflects the warmed cache
   (null for not-yet-warmed voices). Keep the existing `model`/`language` filters as-is.

3. **Preview endpoint** (new route, `request: Request`, no auth dependency):
   ```python
   from fastapi import Request
   from fastapi.responses import FileResponse
   from ..config import get_settings
   from ..voice_store import voice_store
   from .. import previews
   import anyio

   def _bearer_ok(request: Request) -> bool:
       h = request.headers.get("authorization", "")
       token = h[7:].strip() if h[:7].lower() == "bearer " else ""
       return token in get_settings().api_key_set

   @router.get("/voices/{model}/{voice_id}/preview", tags=["voices"],
               summary="Nghe thử giọng (preset: công khai; clone: cần key)")
   async def voice_preview(model: str, voice_id: str, request: Request) -> FileResponse:
       is_clone = voice_store.get(voice_id) is not None
       if is_clone and not _bearer_ok(request):
           raise HTTPException(status_code=401, detail={
               "message": "API key required to preview a cloned voice.",
               "type": "invalid_request_error", "code": "invalid_api_key"})
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
   ```
   Generation is bounded inside `ensure_preview` (`_GEN_SEM`), so the route never
   holds a `synth_semaphore` permit → no priority inversion against paid TTS/ASR.

4. Route order: `GET /voices` (list) and `GET /voices/{model}/{voice_id}/preview`
   do not overlap — no ordering hazard.

## Todo

- [ ] Extend `VoiceInfo` with `preview_url` + `preview_base64`.
- [ ] List endpoint: `preview` query param; `preview_url` for all; base64 cached-only.
- [ ] `voice_preview` route: clone→key(401)/preset→public branch, `is_current` hot path, `ensure_preview` on miss/stale, split Cache-Control, 404 guard.
- [ ] `uv run ruff check app/routers/voices.py app/schemas.py` clean.

## Success Criteria

- [ ] `GET /v1/voices` → each item has a non-empty `preview_url`; `preview_base64` null without the query param.
- [ ] `GET /v1/voices?preview=base64` → cached previews base64-decode to their served bytes; not-yet-warmed voices are null (no synth triggered by the list call).
- [ ] `GET /v1/voices/{preset model}/{preset id}/preview` **without** a key → 200, `audio/mpeg`, `Cache-Control: public, max-age=86400`.
- [ ] `GET /v1/voices/{clone model}/{clone id}/preview` **without** a key → 401; **with** a valid key → 200, `Cache-Control: private, no-store`.
- [ ] `GET /v1/voices/faketts/ghost/preview` → 404 `preview_not_found`; `GET /v1/voices/nope/x/preview` → 404.
- [ ] After a passage change, the URL endpoint serves the NEW audio (staleness via `is_current`), not the old file.

## Risk Assessment

- **Clone detection = `voice_store.get(voice_id) is not None`.** Signal: a clone treated as a preset (served public). Response: clones live only in `voice_store` (voices_admin.py:109) and presets never do, so the check is exact; a clone enrolled on another worker is also visible because `voice_store.get` re-reads registry.json (voice_store.py:97-99).
- **Preset existence oracle** remains (200 vs 404 for presets, no rate limit). Threat model: presets are a fixed, non-sensitive catalog already listed by the authed `/v1/voices`; leaking "preset X exists" has no privacy value. Documented non-issue; a per-IP limit is out of scope.
- **Browser can't send a header for a clone `<audio src>`.** Accepted trade-off from the auth decision: clone previews are for authed clients (or via the authed `/v1/voices?preview=base64`), not public browser demo. Documented in the field help.
