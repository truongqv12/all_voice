"""Pydantic request/response models — kept schema-compatible with the OpenAI
Audio Speech API so the official `openai` SDK works unmodified."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class SpeechRequest(BaseModel):
    """Body của POST /v1/audio/speech (khớp schema OpenAI).

    `model` lạ rơi về backend mặc định, `voice` lạ/kiểu `alloy` rơi về giọng preset
    đầu tiên của backend, nên SDK OpenAI gốc chạy không cần sửa. `style` (knob tinh
    chỉnh duy nhất giữ lại) là phần mở rộng của OpenAI: gửi qua `extra_body` của SDK.
    Mọi knob sampling (temperature/top_k/top_p/…) cố ý không phơi ra — VieNeu tự lo
    nội bộ.
    """

    model: str = Field(
        description="Tên backend, vd `vieneu` / `kokoro` / `voicevox`. Tên lạ (`tts-1`) route về backend mặc định.",
        examples=["vieneu"],
    )
    input: str = Field(
        min_length=1, max_length=4096,
        description="Văn bản cần đọc (≤ 4096 ký tự). Dấu câu tạo ngắt nghỉ; nhúng cue như `[cười]`; chuyển ngữ Việt⇄Anh chạy inline.",
        examples=["Xin chào, đây là all-voice."],
    )
    # OpenAI accepts a voice name string OR a custom-voice object {"id": "..."}.
    voice: str | dict[str, Any] = Field(
        description="Tên preset (vd `Trúc Ly`), id giọng clone (`voice_...`), hoặc object `{\"id\": \"voice_...\"}`.",
        examples=["Trúc Ly"],
    )
    response_format: ResponseFormat = Field(
        default="mp3", description="Định dạng đầu ra: mp3/opus/aac/flac/wav/pcm.",
    )
    # Accepted for OpenAI compatibility. Forwarded to the backend but only
    # honoured if that backend has native speed control; VieNeu does not, so it
    # is a no-op there (the gateway no longer time-stretches — it degraded speech).
    speed: float = Field(
        default=1.0, ge=0.25, le=4.0,
        description="Tốc độ đọc 0.25–4.0 (tương thích OpenAI). Chỉ backend có điều chỉnh tốc độ gốc mới áp dụng; VieNeu bỏ qua.",
    )
    # Accepted for OpenAI compatibility; not applied by every backend yet.
    instructions: str | None = Field(
        default=None, description="Chấp nhận để tương thích OpenAI; chưa phải backend nào cũng áp dụng.",
    )

    # --- Backend tuning knobs (OpenAI extension; pass via `extra_body`). ---
    # `style` is provider-neutral now: the schema accepts any string and the
    # target backend validates it (VieNeu: tu_nhien/tin_tuc/doc_truyen). Sampling
    # params stay backend-internal.
    style: str | None = Field(
        default=None,
        description="Kiểu đọc; giá trị hợp lệ do backend quy định (VieNeu: tu_nhien / tin_tuc / doc_truyen). Backend từ chối giá trị lạ bằng 400.",
    )
    # Free-form bag for engine-specific params (e.g. a future VoiceVox
    # `speedScale`) so a new engine's knobs pass through without a schema change.
    extra: dict[str, Any] | None = Field(
        default=None,
        description="Phần mở rộng OpenAI: tham số riêng của backend (qua extra_body). Backend bỏ qua khóa nó không hiểu.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "vieneu",
                    "input": "Ngày xửa ngày xưa, ở một ngôi làng nhỏ...",
                    "voice": "Trúc Ly",
                    "response_format": "mp3",
                    "speed": 1.0,
                    "style": "doc_truyen",
                }
            ]
        }
    }

    #: Named knobs overlaid onto `extra` when building backend options.
    _OPTION_KEYS = ("style",)

    def backend_options(self) -> dict[str, Any]:
        """Tuning options for the backend: `extra` plus any non-null named knob.

        A named knob (`style`) overrides the same key in `extra`."""
        opts = dict(self.extra or {})
        for k in self._OPTION_KEYS:
            if (v := getattr(self, k)) is not None:
                opts[k] = v
        return opts

    @field_validator("voice")
    @classmethod
    def _normalize_voice(cls, v: str | dict[str, Any]) -> str:
        if isinstance(v, dict):
            voice_id = v.get("id")
            if not voice_id:
                raise ValueError("voice object must contain a non-empty 'id'")
            return str(voice_id)
        return v


class VoiceInfo(BaseModel):
    id: str
    name: str
    model: str
    language: str = "vi"
    styles: list[str] = Field(default_factory=list)
    preview_url: str = Field(
        default="",
        description="Đường dẫn nghe thử (mp3) — công khai, không cần key (cả preset lẫn clone).",
    )
    preview_base64: str | None = Field(
        default=None,
        description="mp3 base64 — chỉ có khi `?preview=base64` và preview đã được tạo sẵn (cache).",
    )


class VoiceList(BaseModel):
    object: str = "list"
    data: list[VoiceInfo]


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "all-voice"


class ModelList(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


class CustomVoice(BaseModel):
    """Object custom-voice của OpenAI (response của POST /v1/audio/voices)."""

    id: str
    created_at: int
    name: str
    object: str = "audio.voice"


class CustomVoiceList(BaseModel):
    object: str = "list"
    data: list[CustomVoice]


class DeletedVoice(BaseModel):
    id: str
    object: str = "audio.voice"
    deleted: bool = True


class VoiceConsent(BaseModel):
    """Object voice-consent của OpenAI (response của POST /v1/audio/voice_consents)."""

    id: str
    created_at: int
    language: str
    name: str
    object: str = "audio.voice_consent"


TranscriptionResponseFormat = Literal["json", "text", "srt", "vtt", "verbose_json"]


class TranscriptionSegment(BaseModel):
    """Một segment có mốc thời gian (≈ một câu) trong transcription `verbose_json` của OpenAI."""

    id: int = Field(description="Chỉ số segment, bắt đầu từ 0.")
    seek: int = Field(description="Offset seek của decoder (frame) — sổ sách nội bộ của Whisper.")
    start: float = Field(description="Thời điểm bắt đầu segment, giây.")
    end: float = Field(description="Thời điểm kết thúc segment, giây.")
    text: str = Field(description="Văn bản nhận dạng của segment này.")
    tokens: list[int] = Field(default_factory=list, description="Token id Whisper của văn bản segment.")
    temperature: float = Field(description="Temperature sampling dùng cho segment này.")
    avg_logprob: float = Field(description="Log-probability trung bình mỗi token (cao ≈ tự tin hơn).")
    compression_ratio: float = Field(description="Tỷ lệ nén gzip; cao bất thường ⇒ có thể là lặp ảo (hallucination).")
    no_speech_prob: float = Field(description="Xác suất segment là im lặng/không phải tiếng nói (0–1).")


class TranscriptionWord(BaseModel):
    """Một từ kèm mốc thời gian (chỉ có khi `timestamp_granularities[]=word`)."""

    word: str = Field(description="Văn bản của từ.")
    start: float = Field(description="Thời điểm bắt đầu từ, giây.")
    end: float = Field(description="Thời điểm kết thúc từ, giây.")


class TranscriptionVerbose(BaseModel):
    """Response `verbose_json` của POST /v1/audio/transcriptions — transcript đầy đủ kèm mốc thời gian."""

    task: str = Field(default="transcribe", description="Luôn là `transcribe` (cổng này không dịch).")
    language: str = Field(description="Mã ngôn ngữ nhận diện (hoặc do bạn cung cấp), vd `vi`.")
    duration: float = Field(description="Độ dài audio, giây.")
    text: str = Field(description="Transcript đầy đủ (gộp mọi segment).")
    segments: list[TranscriptionSegment] = Field(description="Mốc thời gian theo từng segment (cấp câu).")
    words: list[TranscriptionWord] | None = Field(
        default=None, description="Mốc thời gian theo từng từ; chỉ có khi `timestamp_granularities[]=word`.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task": "transcribe",
                    "language": "vi",
                    "duration": 3.92,
                    "text": "Xin chào, đây là all-voice.",
                    "segments": [
                        {
                            "id": 0, "seek": 0, "start": 0.0, "end": 3.92,
                            "text": "Xin chào, đây là all-voice.",
                            "tokens": [50364, 1234, 5678],
                            "temperature": 0.0, "avg_logprob": -0.21,
                            "compression_ratio": 1.1, "no_speech_prob": 0.01,
                        }
                    ],
                    "words": None,
                }
            ]
        }
    }


class Transcription(BaseModel):
    """Response `json` mặc định: chỉ có văn bản transcript."""

    text: str = Field(description="Transcript đầy đủ.", examples=["Xin chào, đây là all-voice."])


class ErrorDetail(BaseModel):
    message: str
    type: str = "invalid_request_error"
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    """Envelope lỗi kiểu OpenAI: {"error": {...}}."""

    error: ErrorDetail
