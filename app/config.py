"""Runtime configuration, loaded from environment / .env (pydantic-settings)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Comma-separated API keys accepted as `Authorization: Bearer <key>`.
    api_keys: str = "dev-key"
    # Device hint passed to backends that support it: cpu | cuda | auto.
    device: str = "cpu"
    # Backend that answers unrecognised (e.g. OpenAI) model names.
    default_backend: str = "vieneu"
    # Upper bound on concurrent synthesis jobs (TTS is CPU-bound). Shared with
    # ASR transcription jobs (see limits.synth_semaphore).
    max_concurrency: int = 2
    # Where cloned-voice samples + registry are persisted.
    voices_dir: str = "data/voices"

    # faster-whisper model for speech-to-text: tiny/base/small/medium/large-v3,
    # or a CTranslate2 repo id (e.g. a PhoWhisper-ct2). `small` balances quality
    # and CPU/RAM cost; downloaded on the first transcribe request (~0.5GB).
    asr_model: str = "small"
    # CTranslate2 compute type: int8 is best for CPU; use float16 on CUDA.
    asr_compute_type: str = "int8"

    host: str = "0.0.0.0"
    # 8123: avoids 8000/8080 which are common and often fall inside Windows'
    # Hyper-V/WSL reserved port ranges (bind -> WinError 10013).
    port: int = 8123

    # Verbosity of the app's operational logs: DEBUG | INFO | WARNING | ERROR.
    log_level: str = "INFO"
    # Directory for the rotating log file (app.log). Empty string = stdout only.
    log_dir: str = "logs"

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
