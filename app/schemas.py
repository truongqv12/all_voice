"""Pydantic request/response models — kept schema-compatible with the OpenAI
Audio Speech API so the official `openai` SDK works unmodified."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class SpeechRequest(BaseModel):
    """Body of POST /v1/audio/speech (mirrors OpenAI's schema).

    Unknown `model` falls back to the default backend and an unknown/`alloy`-style
    `voice` falls back to the backend's first preset, so the stock OpenAI SDK works
    unmodified. `style` (the one tuning knob kept) is an OpenAI extension: pass it
    via the SDK's `extra_body`. All sampling knobs (temperature/top_k/top_p/…) are
    intentionally not exposed — VieNeu manages them internally.
    """

    model: str = Field(
        description="Backend name, e.g. `vieneu`. Unknown names (`tts-1`) route to the default backend.",
        examples=["vieneu"],
    )
    input: str = Field(
        min_length=1, max_length=4096,
        description="Text to speak (≤ 4096 chars). Punctuation drives pauses; embed cues like `[cười]`; Vietnamese⇄English code-switching works inline.",
        examples=["Xin chào, đây là all-voice."],
    )
    # OpenAI accepts a voice name string OR a custom-voice object {"id": "..."}.
    voice: str | dict[str, Any] = Field(
        description="Preset name (e.g. `Trúc Ly`), a cloned-voice id (`voice_...`), or an object `{\"id\": \"voice_...\"}`.",
        examples=["Trúc Ly"],
    )
    response_format: ResponseFormat = Field(
        default="mp3", description="Output container: mp3/opus/aac/flac/wav/pcm.",
    )
    # Accepted for OpenAI compatibility. Forwarded to the backend but only
    # honoured if that backend has native speed control; VieNeu does not, so it
    # is a no-op there (the gateway no longer time-stretches — it degraded speech).
    speed: float = Field(
        default=1.0, ge=0.25, le=4.0,
        description="Playback speed 0.25–4.0 (OpenAI-compatible). Honoured only by backends with native speed control; VieNeu ignores it.",
    )
    # Accepted for OpenAI compatibility; not applied by every backend yet.
    instructions: str | None = Field(
        default=None, description="Accepted for OpenAI compatibility; not applied by every backend yet.",
    )

    # --- Backend tuning knob (OpenAI extension; pass via `extra_body`). ---
    # Only `style` is exposed; sampling params are left to VieNeu's own defaults.
    style: Literal["tu_nhien", "tin_tuc", "doc_truyen"] | None = Field(
        default=None, description="Reading style: tu_nhien (natural) / tin_tuc (news) / doc_truyen (storytelling).",
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

    #: Keys forwarded to the backend as tuning options.
    _OPTION_KEYS = ("style",)

    def backend_options(self) -> dict[str, Any]:
        """Non-null tuning options to hand to the backend."""
        return {k: v for k in self._OPTION_KEYS if (v := getattr(self, k)) is not None}

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
    """OpenAI custom-voice object (POST /v1/audio/voices response)."""

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
    """OpenAI voice-consent object (POST /v1/audio/voice_consents response)."""

    id: str
    created_at: int
    language: str
    name: str
    object: str = "audio.voice_consent"


TranscriptionResponseFormat = Literal["json", "text", "srt", "vtt", "verbose_json"]


class TranscriptionSegment(BaseModel):
    """One timed segment in an OpenAI `verbose_json` transcription."""

    id: int
    seek: int
    start: float
    end: float
    text: str
    tokens: list[int] = Field(default_factory=list)
    temperature: float
    avg_logprob: float
    compression_ratio: float
    no_speech_prob: float


class TranscriptionWord(BaseModel):
    """One word with timing (present when `timestamp_granularities[]=word`)."""

    word: str
    start: float
    end: float


class TranscriptionVerbose(BaseModel):
    """OpenAI `verbose_json` response (POST /v1/audio/transcriptions)."""

    task: str = "transcribe"
    language: str
    duration: float
    text: str
    segments: list[TranscriptionSegment]
    words: list[TranscriptionWord] | None = None


class Transcription(BaseModel):
    """OpenAI default `json` response: just the transcript text."""

    text: str


class ErrorDetail(BaseModel):
    message: str
    type: str = "invalid_request_error"
    param: str | None = None
    code: str | None = None


class ErrorResponse(BaseModel):
    """OpenAI-style error envelope: {"error": {...}}."""

    error: ErrorDetail
