"""Operational logging for debugging (no DB).

One `all_voice.*` logger tree writes concise lines to **stdout** and, unless
disabled, to a rotating **file** (`<log_dir>/app.log`): startup summary,
per-request latency, per-synthesis detail, and 500 tracebacks. Rotation caps
disk use. `faulthandler` is enabled so a native crash (segfault in torch/onnx)
still dumps a C+Python traceback to stderr. Uvicorn's own logs stay as-is."""

from __future__ import annotations

import faulthandler
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False

_FMT = logging.Formatter("%(asctime)s %(levelname)-5s %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB per file
_BACKUPS = 5


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """Configure the `all_voice` logger tree (idempotent).

    stdout is always attached. If `log_dir` is non-empty, a rotating file
    handler at `<log_dir>/app.log` is added too (best-effort: a directory that
    cannot be created falls back to stdout-only).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_dir:
        try:
            path = Path(log_dir)
            path.mkdir(parents=True, exist_ok=True)
            handlers.append(
                RotatingFileHandler(
                    path / "app.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
                )
            )
        except OSError:
            pass  # keep serving on stdout even if the log dir is unwritable

    for h in handlers:
        h.setFormatter(_FMT)

    logger = logging.getLogger("all_voice")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = handlers
    logger.propagate = False  # don't double-print through the root logger

    # Native fatal errors (segfaults) don't go through logging -> dump to stderr.
    if not faulthandler.is_enabled():
        faulthandler.enable()

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Child logger, e.g. get_logger('request') -> `all_voice.request`."""
    return logging.getLogger(f"all_voice.{name}")
