"""Global concurrency guard for CPU-bound synthesis."""

from __future__ import annotations

import anyio

from .config import get_settings

# Caps concurrent synthesis jobs so we don't oversubscribe CPU cores.
synth_semaphore = anyio.Semaphore(get_settings().max_concurrency)
