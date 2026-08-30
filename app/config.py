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

    # Bind to loopback by default: the API is meant to sit hidden behind nginx +
    # Cloudflare Tunnel (see docs/deployment.md). Only nginx (also on localhost)
    # should reach it. This is the fail-closed default (#1); set HOST=0.0.0.0 only
    # for a deliberately LAN-exposed dev box, never for the public deploy.
    host: str = "127.0.0.1"
    # 8123: avoids 8000/8080 which are common and often fall inside Windows'
    # Hyper-V/WSL reserved port ranges (bind -> WinError 10013).
    port: int = 8123
    # uvicorn worker count. MUST stay 1 while anon is enabled: the rate/budget
    # gate is per-process in-memory and SQLite is single-writer, so WORKERS>1
    # multiplies every limit by N and turns the quota DB into a multi-writer race
    # (create_app refuses to start in that combination — see main.py).
    workers: int = 1

    # --- Anonymous (no-key) tier + abuse gate (Phase 1) ---
    # Master switch. True: TTS/ASR run without a key (ANON tier); a valid key is a
    # higher TRUSTED tier. False: no key -> 401 (key-only service, old behaviour).
    anon_enabled: bool = True
    # Token-bucket rate limit per IP: `anon_rate_per_min` tokens/min, bucket
    # capacity `anon_burst`. TRUSTED keys bypass this.
    anon_rate_per_min: int = 10
    anon_burst: int = 10
    # Daily cost budget per IP (resets at UTC midnight). TTS is billed in
    # characters, ASR in seconds of audio — the units of real CPU cost.
    anon_chars_per_day: int = 50_000
    anon_audio_seconds_per_day: int = 1_800
    # SQLite file holding the per-IP daily budget (survives restart).
    quota_db_path: str = "data/quota.db"
    # Max characters for a single buffered /v1/audio/speech request on the ANON
    # tier. Longer input -> 400 pointing at /v1/audio/stream (keeps one synth under
    # Cloudflare's 100s edge timeout — CF 524). TRUSTED is bounded only by the
    # OpenAI-compatible schema max (4096).
    anon_max_chars_buffered: int = 1200
    # Per-IP concurrency + global admission queue. Over either -> 429 immediately
    # (never an unbounded wait). `request_timeout_s` bounds the wait for a synth
    # slot, not the synth itself (a running thread can't be cancelled — #3).
    anon_max_concurrent_per_ip: int = 2
    max_queue_waiters: int = 20
    request_timeout_s: float = 90.0
    # Max simultaneously-open streams per IP for /v1/audio/stream (Phase 3, #8).
    anon_max_streams_per_ip: int = 2
    # IP normalisation before it becomes a bucket/budget key (#9): collapse an
    # IPv6 address to its /64 (a single client owns a whole /64) so address
    # rotation inside one allocation can't dodge the budget. IPv4 stays /32.
    ip_key_ipv6_prefix: int = 64
    # TTL for the in-memory rate-bucket map so idle IPs are evicted and the map
    # stays bounded (#9).
    ip_map_ttl_s: int = 3_600

    # --- Core hardening: thread caps + result cache + ASR duration (Phase 2) ---
    # The OMP inference-thread cap is NOT a Settings field: it must be applied
    # before onnxruntime/CTranslate2 import (app/__init__.py reads the
    # INFERENCE_THREADS env var there), and pydantic loads .env too late for that.
    # Set it as a real env var — the systemd unit does. The real preset CPU cap is
    # the cgroup CPUQuota (#13); the OMP env is defence in depth.
    # CTranslate2 thread count for faster-whisper (a real, honoured param, unlike
    # the preset OMP path). 0 lets CT2 pick (4).
    asr_cpu_threads: int = 4
    # Disk cache of encoded buffered-TTS results (dedup identical text+voice+format).
    # Streaming (/v1/audio/stream) is never cached. Safe to delete.
    result_cache_enabled: bool = True
    result_cache_dir: str = "data/cache"
    # Eviction ceilings for the result cache (background sweep, access-order LRU).
    result_cache_max_mb: int = 512
    result_cache_max_files: int = 4_000
    # Max audio duration (seconds) an ANON request may transcribe. Longer -> 413
    # before any CPU is spent (#7).
    anon_max_audio_seconds: int = 300

    # --- Streaming long-read (Phase 3) ---
    # Max total characters for one /v1/audio/stream request on the ANON tier.
    anon_max_chars_stream: int = 20_000
    # Sentence chunks longer than this are split further so each synth stays short
    # (well under the CF edge timeout) and a disconnect stops the stream promptly.
    stream_max_chunk_chars: int = 400

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
    # Path to the VOICEVOX ONNX Runtime shared library. The pip wheel bundles NO
    # runtime, so it must be loaded from a file; `scripts/fetch-voicevox.sh`
    # downloads it here and drops a version-independent symlink. Set "" only to
    # fall back to a runtime already discoverable on the loader path.
    voicevox_onnxruntime: str = "models/voicevox/onnxruntime/lib/libvoicevox_onnxruntime.so"
    # Comma-separated `style_id` or `speaker_uuid:style_id` allowed on the API;
    # empty = expose every style found in the loadable VVMs.
    voicevox_speaker_allowlist: str = ""

    # --- Voice previews ("nghe thử") ---
    # Where per-voice preview mp3s + sidecars are cached (safe to delete;
    # regenerates on next request/warm).
    previews_dir: str = "data/previews"
    # Warm the default backend's presets + existing clones at startup (background
    # thread, non-blocking). VOICEVOX/Kokoro stay lazy.
    preview_warm_on_startup: bool = True
    # Dedicated CPU budget for preview generation, kept OFF synth_semaphore so
    # previews never starve paid /v1/audio/speech + ASR. 1 = one preview synth at a time.
    preview_concurrency: int = 1
    # Standard passage per language; empty string = use the built-in default.
    preview_text_vi: str = ""
    preview_text_en: str = ""
    preview_text_ja: str = ""

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
