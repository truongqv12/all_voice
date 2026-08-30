"""all-voice: OpenAI-compatible, multi-backend TTS gateway."""

import os

# Cap inference threads BEFORE any heavy library (onnxruntime / CTranslate2) is
# imported — they read OMP_NUM_THREADS at import time, so setting it later is a
# no-op. `setdefault` lets a systemd `Environment=OMP_NUM_THREADS=` (the
# authoritative lever, Phase 4) win. NOTE (#13): the VieNeu preset path is ONNX
# torch-free and may ignore OMP entirely — its real CPU cap is cgroup CPUQuota /
# taskset in the unit file; this is defence in depth, not the whole story.
os.environ.setdefault("OMP_NUM_THREADS", os.environ.get("INFERENCE_THREADS", "4"))

__version__ = "0.1.1"
