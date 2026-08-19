"""Custom (cloned) voice management — OpenAI-compatible.

    POST   /v1/audio/voices            enrol a cloned voice from an audio sample
    GET    /v1/audio/voices            list cloned voices
    GET    /v1/audio/voices/{id}       retrieve one
    DELETE /v1/audio/voices/{id}       delete one
    POST   /v1/audio/voice_consents    issue a consent id (accepted for OpenAI
                                       compatibility; not legally enforced here)

Deviations from OpenAI (self-hosted gateway, VieNeu-backed): `consent` is
optional on voice creation, and consent recordings are not persisted."""

from __future__ import annotations

import os
import secrets
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..auth import require_api_key
from ..backends.base import VoiceBackend
from ..backends.registry import registry
from ..schemas import CustomVoice, CustomVoiceList, DeletedVoice, VoiceConsent
from ..voice_store import voice_store

router = APIRouter()

MAX_SAMPLE_BYTES = 10 * 1024 * 1024  # OpenAI limit: 10 MiB


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"message": message, "type": "invalid_request_error", "code": code},
    )


def _cloning_backend() -> VoiceBackend:
    """Default backend if it clones, else the first cloning-capable backend."""
    default = registry.get(None)
    if default is not None and default.supports_cloning:
        return default
    for name in registry.models():
        backend = registry.get(name)
        if backend is not None and backend.supports_cloning:
            return backend
    raise _error(400, "No voice-cloning backend is available.", "cloning_unsupported")


@router.post("/audio/voices", response_model=CustomVoice, tags=["voices"], summary="Create a cloned voice")
async def create_voice(
    name: str = Form(...),
    audio_sample: UploadFile = File(...),
    id: str | None = Form(
        default=None,
        description="Optional custom voice ID (e.g. `voice_mc_nam`). If omitted, a random `voice_...` ID is generated.",
    ),
    consent: str | None = Form(default=None),  # optional (OpenAI requires it)
    denoise: bool = Form(
        default=True,
        description="Denoise the reference. Leave on for noisy clips; turn OFF for already-clean samples to preserve the original timbre (better clone fidelity).",
    ),
    _key: str = Depends(require_api_key),
) -> CustomVoice:
    sample = await audio_sample.read()
    if not sample:
        raise _error(400, "audio_sample is empty.", "invalid_audio_sample")
    if len(sample) > MAX_SAMPLE_BYTES:
        raise _error(400, "audio_sample exceeds the 10 MiB limit.", "audio_sample_too_large")

    custom_id = id.strip() if id and id.strip() else None
    if custom_id:
        import re
        if not re.fullmatch(r"^[a-zA-Z0-9_-]{1,64}$", custom_id):
            raise _error(
                400,
                "Voice ID must contain only alphanumeric characters, underscores, and hyphens (1-64 chars).",
                "invalid_voice_id",
            )

    backend = _cloning_backend()
    suffix = os.path.splitext(audio_sample.filename or "")[1] or ".wav"
    # use_ref_codes is no longer a user knob; it stays on (True) internally for
    # best clone fidelity via the VoiceRecord default.
    record = voice_store.create(
        name=name, sample=sample, suffix=suffix, backend=backend.name,
        denoise=denoise, voice_id=custom_id,
    )
    try:
        backend.register_voice(
            record.id, record.name, record.sample_path,
            denoise=record.denoise, use_ref_codes=record.use_ref_codes,
        )
    except Exception as exc:  # enrolment failed -> don't leave a dangling record
        voice_store.delete(record.id)
        raise _error(400, f"Voice enrolment failed: {exc}", "voice_enrolment_failed")

    return CustomVoice(id=record.id, created_at=record.created_at, name=record.name)


@router.get("/audio/voices", response_model=CustomVoiceList, tags=["voices"], summary="List cloned voices")
async def list_custom_voices(_key: str = Depends(require_api_key)) -> CustomVoiceList:
    data = [
        CustomVoice(id=r.id, created_at=r.created_at, name=r.name) for r in voice_store.list()
    ]
    return CustomVoiceList(data=data)


@router.get("/audio/voices/{voice_id}", response_model=CustomVoice, tags=["voices"], summary="Retrieve a cloned voice")
async def get_custom_voice(voice_id: str, _key: str = Depends(require_api_key)) -> CustomVoice:
    record = voice_store.get(voice_id)
    if record is None:
        raise _error(404, f"Voice '{voice_id}' not found.", "voice_not_found")
    return CustomVoice(id=record.id, created_at=record.created_at, name=record.name)


@router.delete("/audio/voices/{voice_id}", response_model=DeletedVoice, tags=["voices"], summary="Delete a cloned voice")
async def delete_custom_voice(voice_id: str, _key: str = Depends(require_api_key)) -> DeletedVoice:
    record = voice_store.get(voice_id)
    if record is not None:
        backend = registry.get(record.backend)
        if backend is not None and backend.supports_cloning:
            backend.remove_voice(voice_id)
        voice_store.delete(voice_id)
        return DeletedVoice(id=voice_id)

    # No store record (e.g. enrolled on another worker/instance whose write we
    # already dropped, or an in-memory-only leftover). If a cloning backend
    # still advertises the voice, remove it there so a voice you can see is a
    # voice you can delete — otherwise it is genuinely unknown.
    for name in registry.models():
        backend = registry.get(name)
        if backend is not None and backend.supports_cloning and backend.remove_voice(voice_id):
            return DeletedVoice(id=voice_id)
    raise _error(404, f"Voice '{voice_id}' not found.", "voice_not_found")


@router.post("/audio/voice_consents", response_model=VoiceConsent, tags=["voices"], summary="Issue a voice consent id")
async def create_voice_consent(
    language: str = Form(...),
    name: str = Form(...),
    recording: UploadFile = File(...),
    _key: str = Depends(require_api_key),
) -> VoiceConsent:
    # Accepted for OpenAI SDK compatibility. Consent is not enforced by this
    # gateway; the recording is read (to validate the upload) but not stored.
    await recording.read()
    return VoiceConsent(
        id="cons_" + secrets.token_hex(12),
        created_at=int(time.time()),
        language=language,
        name=name,
    )
