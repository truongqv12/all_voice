"""FastAPI application factory: register backends, mount routers, shape errors."""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .backends.registry import registry
from .backends.vieneu_backend import VieNeuBackend
from .config import get_settings
from .docs_ui import get_audio_swagger_ui_html
from .logging_config import get_logger, setup_logging
from .routers import models, speech, voices, voices_admin
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


def _reenrol_cloned_voices() -> None:
    """Re-load persisted cloned voices into their backends after a restart."""
    for record in voice_store.list():
        backend = registry.get(record.backend)
        if backend is not None and backend.supports_cloning:
            try:
                backend.register_voice(
                    record.id, record.name, record.sample_path,
                    denoise=record.denoise, use_ref_codes=record.use_ref_codes,
                )
            except Exception:  # a bad/missing sample must not block startup
                continue


API_DESCRIPTION = """
OpenAI-compatible, multi-backend Text-to-Speech gateway (first backend: **VieNeu-TTS**, Vietnamese).

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
        "ready | version=%s device=%s backends=%s cloned_voices=%d max_concurrency=%d",
        __version__, settings.device, registry.models(), len(voice_store.list()), settings.max_concurrency,
    )

    app.include_router(speech.router, prefix="/v1")
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
