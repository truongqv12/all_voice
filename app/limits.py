"""Global concurrency guard for CPU-bound jobs (TTS synthesis + ASR transcription)."""

from __future__ import annotations

import anyio

from .config import get_settings

# Caps concurrent CPU-bound jobs so we don't oversubscribe cores. Shared by both
# TTS synthesis and ASR transcription: they draw from one MAX_CONCURRENCY budget,
# so a busy box can raise MAX_CONCURRENCY to widen it for both.
synth_semaphore = anyio.Semaphore(get_settings().max_concurrency)
