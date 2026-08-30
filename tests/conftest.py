"""Shared test helpers for the synthesis suites.

`assert_real_audio` / `save_wav` are plain module-level functions (imported as
`from conftest import ...`); pytest puts this file's directory on sys.path. Heavy
imports (soundfile) are done lazily so the fast `-m "not synth"` run works on a
base install without the `en`/`ja` extras.
"""

from __future__ import annotations

import os
import tempfile

# Disable preview warm globally so importing app.main (app = create_app()) stays
# instant and never spawns a background synth thread during tests.
os.environ.setdefault("PREVIEW_WARM_ON_STARTUP", "false")
# Keep the anon gate's SQLite budget + result cache OUT of the real data/ dir so
# tests never pollute production state (set before app import).
_TMP = tempfile.gettempdir()
os.environ.setdefault("QUOTA_DB_PATH", os.path.join(_TMP, "all_voice_test_quota.db"))
os.environ.setdefault("RESULT_CACHE_DIR", os.path.join(_TMP, "all_voice_test_cache"))

from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402

OUTPUT_DIR = Path(__file__).parent / "output"


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture(autouse=True)
def _reset_gate():
    """Reset the process-wide anon gate between tests so one test's rate-bucket /
    concurrency state never leaks into the next (all keyed by the shared
    `testclient` IP under TestClient)."""
    from app.limits import reset_state
    from app.quota import quota

    with quota._bucket_lock:
        quota._buckets.clear()
    reset_state()
    yield


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
