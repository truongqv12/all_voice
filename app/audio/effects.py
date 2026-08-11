"""Backend-agnostic audio effects applied by the gateway.

`speed` is honoured here (not in the backend) so it works uniformly for every
engine — including VieNeu, which has no native speed control. Uses a
pitch-preserving time-stretch (phase vocoder)."""

from __future__ import annotations

import librosa
import numpy as np


def apply_speed(pcm: np.ndarray, speed: float) -> np.ndarray:
    """Time-stretch mono float32 PCM by `speed` (2.0 = twice as fast), keeping
    pitch. `speed == 1.0` is a no-op."""
    if speed == 1.0:
        return pcm
    stretched = librosa.effects.time_stretch(y=np.asarray(pcm, dtype=np.float32), rate=speed)
    return np.asarray(stretched, dtype=np.float32)
