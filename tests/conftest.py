"""Shared test helpers for the synthesis suites.

`assert_real_audio` / `save_wav` are plain module-level functions (imported as
`from conftest import ...`); pytest puts this file's directory on sys.path. Heavy
imports (soundfile) are done lazily so the fast `-m "not synth"` run works on a
base install without the `en`/`ja` extras.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.config import get_settings

OUTPUT_DIR = Path(__file__).parent / "output"


@pytest.fixture
def settings():
    return get_settings()


def assert_real_audio(pcm, sr, *, min_rms: float = 1e-3, expected_sr: int = 24000) -> float:
    """Assert `pcm`/`sr` is genuine mono float32 audio (not silence) and return RMS."""
    pcm = np.asarray(pcm)
    assert pcm.ndim == 1, f"expected mono 1-D pcm, got shape {pcm.shape}"
    assert pcm.dtype == np.float32, f"expected float32, got {pcm.dtype}"
    assert sr == expected_sr, f"expected sample_rate {expected_sr}, got {sr}"
    assert len(pcm) > 0.2 * sr, f"audio too short: {len(pcm)} samples at {sr}Hz"
    rms = float(np.sqrt(np.mean(np.square(pcm))))
    assert rms > min_rms, f"audio looks silent: rms={rms:.2e} <= {min_rms:.2e}"
    return rms


def save_wav(pcm, sr, name: str) -> Path:
    """Write PCM to tests/output/<name> for manual listening; print the path."""
    import soundfile as sf

    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / name
    sf.write(path, np.asarray(pcm, dtype=np.float32), sr)
    print(f"\n[saved] {path}")
    return path
