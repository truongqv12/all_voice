"""POST /v1/audio/transcriptions — OpenAI-compatible speech-to-text.

Thin router over `app/asr`: multipart in, transcript out in the requested
`response_format` (json/text/srt/vtt/verbose_json). Reuses the shared auth,
CPU-budget semaphore, and OpenAI error envelope; never touches the TTS core.
"""

from __future__ import annotations

import time
from functools import partial

import anyio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from ..asr import (
    AsrUnavailableError,
    InvalidAudioError,
    to_json,
    to_srt,
    to_verbose_json,
    to_vtt,
    transcribe,
)
from ..auth import require_api_key
from ..limits import synth_semaphore
from ..logging_config import get_logger
from ..schemas import TranscriptionResponseFormat, TranscriptionVerbose

router = APIRouter()
log = get_logger("transcribe")

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # OpenAI limit: 25 MiB
_PLAIN = "text/plain; charset=utf-8"


def _error(status_code: int, message: str, code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"message": message, "type": "invalid_request_error", "code": code},
    )


@router.post(
    "/audio/transcriptions",
    tags=["transcriptions"],
    summary="Tạo bản ghi (transcription)",
    responses={
        200: {
            "model": TranscriptionVerbose,
            "description": (
                "Transcript theo `response_format` yêu cầu: `json` -> `{\"text\": ...}`; "
                "`verbose_json` -> mốc thời gian đầy đủ theo segment/từ (xem schema); "
                "`text`/`srt`/`vtt` -> văn bản thuần."
            ),
        },
        400: {"description": "Yêu cầu không hợp lệ (file rỗng/không giải mã được, quá lớn, tham số sai)."},
        401: {"description": "Thiếu hoặc sai API key."},
        503: {"description": "Chưa cài engine ASR (`uv sync --extra asr`)."},
    },
)
async def create_transcription(
    file: UploadFile = File(
        ...,
        description="File audio cần nhận dạng (mp3/wav/m4a/ogg/flac/webm…, ≤ 25 MiB). Giải mã qua ffmpeg/av.",
    ),
    # Accepted for OpenAI compatibility; a single configured engine answers every
    # model name (logged, not routed).
    model: str = Form(
        "whisper-1",
        description="Chấp nhận để tương thích OpenAI. Tên nào cũng được — engine đã cấu hình (env `ASR_MODEL`, mặc định `small`) luôn trả lời.",
    ),
    language: str | None = Form(
        None, description="Gợi ý ISO-639-1 (vd `vi`) để bỏ qua auto-detect. Bỏ trống = tự nhận diện.",
    ),
    response_format: TranscriptionResponseFormat = Form(
        "json",
        description=(
            "Định dạng đầu ra: `json` → `{\"text\": ...}` (mặc định) · `text` → transcript thô · "
            "`srt`/`vtt` → file phụ đề (mốc theo segment) · `verbose_json` → mốc đầy đủ theo segment (+từ)."
        ),
    ),
    prompt: str | None = Form(
        None,
        description="Văn bản tùy chọn để định hướng cách giải mã theo thuật ngữ/cách viết cụ thể (map sang `initial_prompt` của Whisper).",
    ),
    temperature: float = Form(
        0.0, ge=0.0, le=1.0,
        description="Temperature giải mã 0.0–1.0. Giữ 0.0 để transcript tất định nhất.",
    ),
    timestamp_granularities: list[str] = Form(
        [],
        alias="timestamp_granularities[]",
        description="Thêm `word` (với `response_format=verbose_json`) để có mảng `words[]` ở cấp cao nhất với mốc từng từ (karaoke). Mốc theo segment luôn có sẵn.",
    ),
    # OpenAI SDKs send the key with `[]`; accept the bare key too for clients that
    # omit the brackets. (FastAPI can't hide a Form field from the multipart body
    # schema, so it's documented as an alias rather than hidden.)
    timestamp_granularities_bare: list[str] = Form(
        [],
        alias="timestamp_granularities",
        description="Alias tương thích cho `timestamp_granularities[]` (client bỏ dấu ngoặc). Nên dùng `timestamp_granularities[]`.",
    ),
    _key: str = Depends(require_api_key),
) -> Response:
    """Nhận dạng giọng nói thành văn bản kèm mốc thời gian — tương thích OpenAI.

    Gửi file audio dạng multipart/form-data và nhận lại transcript theo
    `response_format` yêu cầu: `text`/`json` thuần, phụ đề `srt`/`vtt` dùng ngay
    (mốc theo câu), hoặc `verbose_json` với mốc theo từng segment (và tùy chọn
    từng từ). Chỉ nhận dạng — không dịch.

    Gọi được không cần sửa qua SDK OpenAI `client.audio.transcriptions.create(...)`.
    Cần extra `asr` (`uv sync --extra asr`); thiếu thì endpoint trả **503**. Engine
    nạp model (env `ASR_MODEL`, mặc định `small`) lazy ở request đầu tiên.
    """
    data = await file.read()
    if not data:
        raise _error(400, "file is empty.", "invalid_audio_file")
    if len(data) > MAX_AUDIO_BYTES:
        raise _error(400, "file exceeds the 25 MiB limit.", "audio_file_too_large")

    granularities = [*timestamp_granularities, *timestamp_granularities_bare]
    want_words = "word" in granularities

    start = time.perf_counter()
    # Transcription is blocking/CPU-bound -> off the event loop, bounded by the
    # shared CPU-budget semaphore (same MAX_CONCURRENCY as TTS synthesis).
    try:
        async with synth_semaphore:
            result = await anyio.to_thread.run_sync(
                partial(
                    transcribe,
                    data,
                    language=language,
                    want_words=want_words,
                    prompt=prompt,
                    temperature=temperature,
                )
            )
    except AsrUnavailableError:
        raise _error(
            503, "ASR engine not installed. Run `uv sync --extra asr`.", "asr_unavailable"
        )
    except InvalidAudioError:
        raise _error(
            400, "Could not decode the audio file. Provide a valid audio file.", "invalid_audio_file"
        )

    if response_format == "text":
        payload: Response = Response(result.text, media_type=_PLAIN)
    elif response_format == "srt":
        payload = Response(to_srt(result.segments), media_type=_PLAIN)
    elif response_format == "vtt":
        payload = Response(to_vtt(result.segments), media_type=_PLAIN)
    elif response_format == "verbose_json":
        payload = JSONResponse(to_verbose_json(result))
    else:  # "json" (default)
        payload = JSONResponse(to_json(result))

    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "transcribe model=%s bytes=%d fmt=%s lang=%s words=%s -> %d segments %.1fs audio in %.0fms",
        model, len(data), response_format, result.language, want_words,
        len(result.segments), result.duration, elapsed_ms,
    )
    return payload
