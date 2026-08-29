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

    # --- Kokoro (English preset TTS) ---
    # Registration still requires the model files present (is_available), so a
    # flag left on with no assets downloaded skips the backend safely.
    enable_kokoro: bool = True
    kokoro_model_path: str = "models/kokoro/kokoro-v1.0.int8.onnx"
    kokoro_voices_path: str = "models/kokoro/voices-v1.0.bin"
    # Preset returned when an OpenAI-generic request falls back leniently.
    kokoro_default_voice: str = "af_heart"

    # --- VOICEVOX (Japanese preset TTS) ---
    enable_voicevox: bool = True
    voicevox_dict_dir: str = "models/voicevox/open_jtalk_dic_utf_8-1.11"
    voicevox_vvm_dir: str = "models/voicevox/vvms"
    # "" = let voicevox_core load the onnxruntime it ships with; else a path.
    voicevox_onnxruntime: str = ""
    # Comma-separated `style_id` or `speaker_uuid:style_id` allowed on the API;
    # empty = expose every style found in the loadable VVMs.
    voicevox_speaker_allowlist: str = ""

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
