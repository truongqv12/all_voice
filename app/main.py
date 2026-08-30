"""FastAPI application factory: register backends, mount routers, shape errors."""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__, asr, result_cache
from .backends.registry import registry
from .backends.vieneu_backend import VieNeuBackend
from .client_identity import client_ip
from .config import get_settings
from .docs_ui import get_audio_swagger_ui_html
from .limits import GateError
from .logging_config import get_logger, setup_logging
from .routers import models, speech, speech_stream, transcriptions, voices, voices_admin
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
Cổng Text-to-Speech **tương thích OpenAI, đa engine**. Mỗi engine đăng ký theo
ngôn ngữ và tự xuất hiện trong `/v1/models` + `/v1/voices` khi asset đã cài:
**VieNeu-TTS** (tiếng Việt, có clone) · **Kokoro-82M** (tiếng Anh, giọng preset) ·
**VOICEVOX** (tiếng Nhật, giọng preset). VieNeu là backend **mặc định** cho các tên
`model` kiểu OpenAI. Chọn ngôn ngữ bằng cách chọn `model` + `voice`.

**Xác thực & tầng truy cập** — khi `ANON_ENABLED=true`, `/v1/audio/speech`, `/v1/audio/stream`
và `/v1/audio/transcriptions` chạy **không cần key** (tầng ANON: rate-limit + budget/ngày
theo IP). Gửi `Authorization: Bearer <key>` (key trong `API_KEYS`) để lên tầng **TRUSTED**
(bỏ qua giới hạn). Khám phá (`GET /v1/voices`, `/v1/models`, nghe thử) **công khai**; tạo/
sửa/xóa giọng clone (`/v1/audio/voices*`) **luôn cần key**. Khi `ANON_ENABLED=false`, mọi
route `/v1/*` (trừ khám phá) cần key.

**Tương thích OpenAI** — SDK `openai` gốc chạy không cần sửa: `model` lạ (vd `tts-1`)
route về backend mặc định, `voice` lạ/kiểu `alloy` rơi về giọng preset đầu tiên.

**Knob tinh chỉnh** — `style` (knob duy nhất được phơi ra) là phần mở rộng của OpenAI;
gửi qua `extra_body` của SDK. Tham số sampling để VieNeu tự lo theo mặc định nội bộ.

Lỗi trả về theo envelope OpenAI: `{"error": {"message", "type", "code"}}`.
""".strip()

TAGS_METADATA = [
    {"name": "speech", "description": "Tổng hợp giọng nói (text-to-speech)."},
    {"name": "transcriptions", "description": "Nhận dạng giọng nói + mốc thời gian phụ đề (SRT/VTT/verbose_json)."},
    {"name": "voices", "description": "Khám phá & quản lý giọng preset + giọng clone (API custom-voice của OpenAI)."},
    {"name": "models", "description": "Các backend đã đăng ký."},
    {"name": "system", "description": "Kiểm tra sống (liveness)."},
]


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir)
    log = get_logger("startup")

    # The anon gate (rate/budget/concurrency) is per-process in-memory + SQLite
    # single-writer, so more than one worker multiplies every limit by N and races
    # the quota DB. Refuse to start in that unsafe combination (#5) — fail-closed
    # rather than silently un-protecting the box.
    if settings.anon_enabled and settings.workers > 1:
        raise RuntimeError(
            f"ANON_ENABLED=true requires WORKERS=1 (got {settings.workers}): the "
            "in-memory rate/budget gate and single-writer SQLite quota are not "
            "safe across workers. Run one worker, or disable anon access."
        )

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

    # Warm previews off the boot path: a background daemon so startup never blocks,
    # and warm_startup() covers only the default backend + clones (VOICEVOX/Kokoro
    # self-heal lazily, preserving their lazy per-style model loading).
    if settings.preview_warm_on_startup:
        import threading

        from . import previews

        threading.Thread(target=previews.warm_startup, name="preview-warm", daemon=True).start()
        log.info("preview warm started (background, default backend + clones)")

    # Background result-cache eviction: an off-hot-path daemon sweep that trims the
    # cache to its size/count ceilings (previews has no size LRU — this is new).
    if settings.result_cache_enabled:
        import threading

        def _cache_sweeper() -> None:
            while True:
                time.sleep(300)
                try:
                    result_cache.evict()
                except Exception as exc:  # a sweep error must never kill the box
                    log.warning("result cache sweep failed: %s", exc)

        threading.Thread(target=_cache_sweeper, name="cache-evict", daemon=True).start()

    app.include_router(speech.router, prefix="/v1")
    app.include_router(speech_stream.router, prefix="/v1")
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
        req_log.info(
            "%s %s ip=%s -> %d (%.0fms)",
            request.method, request.url.path, client_ip(request, settings),
            response.status_code, elapsed_ms,
        )
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

    @app.exception_handler(GateError)
    async def _gate_rejected(_: Request, exc: GateError) -> JSONResponse:
        # Rate limit / budget / overload -> 429 with the OpenAI error envelope.
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": str(exc), "type": "rate_limit_error", "code": exc.code}},
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

    @app.get("/health", tags=["system"], summary="Kiểm tra sống")
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
