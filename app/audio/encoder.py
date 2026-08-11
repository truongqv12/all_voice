"""Encode mono float32 PCM into any OpenAI `response_format`.

wav/pcm use the standard library; mp3/opus/aac/flac use PyAV (bundled FFmpeg
libraries — no system FFmpeg required). One entry point: `encode()`."""

from __future__ import annotations

import io
import wave

import av
import numpy as np

CONTENT_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}

# format -> (container, codec, sample_fmt) for the PyAV path.
_AV_FORMATS: dict[str, tuple[str, str, str]] = {
    "mp3": ("mp3", "mp3", "fltp"),
    "aac": ("adts", "aac", "fltp"),
    "opus": ("ogg", "libopus", "s16"),
    "flac": ("flac", "flac", "s16"),
}


def content_type_for(fmt: str) -> str:
    return CONTENT_TYPES[fmt]


def _to_int16(pcm: np.ndarray) -> np.ndarray:
    return (np.clip(pcm, -1.0, 1.0) * 32767.0).astype("<i2")


def _encode_wav(pcm: np.ndarray, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(_to_int16(pcm).tobytes())
    return buf.getvalue()


def _encode_pcm(pcm: np.ndarray, sample_rate: int) -> bytes:
    # Raw 16-bit little-endian PCM, mono, no header (rate == backend rate).
    return _to_int16(pcm).tobytes()


def _make_frame(pcm: np.ndarray, sample_rate: int, sample_fmt: str) -> av.AudioFrame:
    if sample_fmt == "fltp":
        arr = np.ascontiguousarray(pcm.reshape(1, -1), dtype=np.float32)
    else:  # s16, packed
        arr = np.ascontiguousarray(_to_int16(pcm).reshape(1, -1))
    frame = av.AudioFrame.from_ndarray(arr, format=sample_fmt, layout="mono")
    frame.rate = sample_rate
    return frame


def _encode_av(pcm: np.ndarray, sample_rate: int, fmt: str) -> bytes:
    container_fmt, codec, sample_fmt = _AV_FORMATS[fmt]
    buf = io.BytesIO()
    output = av.open(buf, mode="w", format=container_fmt)
    try:
        stream = output.add_stream(codec, rate=sample_rate)
        # Feed via a FIFO so we hand the encoder frames of its required size.
        fifo = av.audio.fifo.AudioFifo()
        fifo.write(_make_frame(pcm, sample_rate, sample_fmt))
        frame_size = getattr(stream, "frame_size", 0) or 1024
        while fifo.samples >= frame_size:
            for packet in stream.encode(fifo.read(frame_size)):
                output.mux(packet)
        if fifo.samples > 0:
            for packet in stream.encode(fifo.read()):
                output.mux(packet)
        for packet in stream.encode(None):  # flush
            output.mux(packet)
    finally:
        output.close()
    return buf.getvalue()


def encode(pcm: np.ndarray, sample_rate: int, fmt: str) -> bytes:
    """Encode PCM into `fmt` bytes. Raises KeyError for an unknown format."""
    pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
    if fmt == "wav":
        return _encode_wav(pcm, sample_rate)
    if fmt == "pcm":
        return _encode_pcm(pcm, sample_rate)
    if fmt in _AV_FORMATS:
        return _encode_av(pcm, sample_rate, fmt)
    raise KeyError(fmt)
