"""FastAPI application factory: register backends, mount routers, shape errors."""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__, asr
from .backends.registry import registry
from .backends.vieneu_backend import VieNeuBackend
from .config import get_settings
from .docs_ui import get_audio_swagger_ui_html
from .logging_config import get_logger, setup_logging
from .routers import models, speech, transcriptions, voices, voices_admin
from .voice_store import voice_store


def _register_backends() -> None:
    settings = get_settings()
    if not VieNeuBackend.is_available():
        raise RuntimeError(
            "VieNeu backend unavailable: `vieneu` is not installed. Run `uv sync`."
        )
    registry.register(
        VieNeuBackend(device=settings.device),
        default=(settings.default_backend in ("vieneu", "")),
    )
    # Optional preset engines: import locally so a missing `en`/`ja` extra never
    # breaks startup. Register only when the flag is on AND the package + model
    # assets are present; otherwise log one line and carry on (VieNeu-only deploy
    # stays intact). Both are non-default — VieNeu keeps answering OpenAI-generic
    # model names.
    log = get_logger("startup")
    if settings.enable_kokoro:
        try:
            from .backends.kokoro_backend import KokoroBackend

            if KokoroBackend.is_available(settings):
                registry.register(KokoroBackend(settings), default=False)
            else:  # flag on but package/model missing -> one line, no raise
                log.info("kokoro not registered: install `en` extra + run scripts/fetch-kokoro.sh")
        except Exception as exc:  # unexpected import/construction error -> skip
            log.warning("kokoro backend skipped: %s", exc)
    if settings.enable_voicevox:
        try:
            from .backends.voicevox_backend import VoicevoxBackend

            if VoicevoxBackend.is_available(settings):
                registry.register(VoicevoxBackend(settings), default=False)
            else:
                log.info("voicevox not registered: install `ja` extra + run scripts/fetch-voicevox.sh")
        except Exception as exc:
            log.warning("voicevox backend skipped: %s", exc)


def _reenrol_cloned_voices() -> None:
    """Re-load persisted cloned voices into their backends after a restart."""
    for record in voice_store.list():
        backend = registry.get(record.backend)
        if backend is not None and backend.supports_cloning:
            try:
                backend.register_voice(
                    record.id, record.name, record.sample_path,
                    denoise=record.denoise, use_ref_codes=record.use_ref_codes,
                    options=record.enrol_options,
                )
            except Exception:  # a bad/missing sample must not block startup
                continue


API_DESCRIPTION = """
OpenAI-compatible, multi-backend Text-to-Speech gateway. Engines register by
language and appear in `/v1/models` + `/v1/voices` as their assets are installed:
**VieNeu-TTS** (Vietnamese, cloning) · **Kokoro-82M** (English presets) ·
**VOICEVOX** (Japanese presets). VieNeu stays the default for OpenAI-generic model
names. Pick a language by picking a `model` + `voice`.

**Auth** — every `/v1/*` route needs `Authorization: Bearer <key>` (keys from the `API_KEYS` env var).

**OpenAI compatibility** — the stock `openai` SDK works unmodified: unknown `model`
(e.g. `tts-1`) routes to the default backend and an unknown/`alloy`-style `voice`
falls back to the first preset.

**Tuning knob** — `style` (the only one exposed) is an OpenAI extension; pass it
via the SDK's `extra_body`. Sampling params are left to VieNeu's internal defaults.

Errors use the OpenAI envelope: `{"error": {"message", "type", "code"}}`.
""".strip()

TAGS_METADATA = [
    {"name": "speech", "description": "Text-to-speech synthesis."},
    {"name": "transcriptions", "description": "Speech-to-text with subtitle timing (SRT/VTT/verbose_json)."},
    {"name": "voices", "description": "Preset + cloned voice discovery and management (OpenAI custom-voice API)."},
    {"name": "models", "description": "Registered backends."},
    {"name": "system", "description": "Liveness."},
]


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir)
    log = get_logger("startup")

    app = FastAPI(
        title="all-voice",
        version=__version__,
        description=API_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url=None,
    )
    _register_backends()
    _reenrol_cloned_voices()
    log.info(
        "ready | version=%s device=%s backends=%s cloned_voices=%d max_concurrency=%d asr_model=%s asr_available=%s",
        __version__, settings.device, registry.models(), len(voice_store.list()),
        settings.max_concurrency, settings.asr_model, asr.is_available(),
    )

    app.include_router(speech.router, prefix="/v1")
    app.include_router(transcriptions.router, prefix="/v1")
    app.include_router(voices.router, prefix="/v1")
    app.include_router(voices_admin.router, prefix="/v1")
    app.include_router(models.router, prefix="/v1")

    req_log = get_logger("request")

    @app.middleware("http")
    async def _log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        req_log.info("%s %s -> %d (%.0fms)", request.method, request.url.path, response.status_code, elapsed_ms)
        return response

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            return JSONResponse(status_code=exc.status_code, content={"error": detail})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": str(detail), "type": "invalid_request_error"}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        message = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()
        )
        return JSONResponse(
            status_code=400,
            content={"error": {"message": message, "type": "invalid_request_error", "code": "invalid_request"}},
        )

    err_log = get_logger("error")

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback for debugging; return the OpenAI error envelope.
        err_log.exception("unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "Internal server error.", "type": "server_error", "code": "internal_error"}},
        )

    @app.get("/health", tags=["system"], summary="Liveness probe")
    async def health() -> dict:
        return {"status": "ok", "models": registry.models()}

    @app.get("/docs", include_in_schema=False)
    async def swagger_docs():
        return get_audio_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
        )

    return app


app = create_app()
