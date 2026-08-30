"""Long-read streaming: split text into sentences and stream synthesized MP3.

`sentence_split` is a dependency-free splitter (no NLP model): it breaks on
sentence terminators, packs short fragments together, and hard-splits any run
longer than `max_len` so every synth call stays short — a few seconds of audio, well
under Cloudflare's edge timeout, and quick to stop when the client disconnects (#3).

`synth_stream` is the async generator behind `POST /v1/audio/stream`. Per chunk it:
checks for client disconnect, reserves that chunk's characters (commit-as-you-yield,
so an interrupted stream is only billed for what it delivered — #4), synthesizes
under the admission gate (released between chunks so other callers interleave), and
feeds the PCM into one continuous MP3 encoder. Every exit path closes the encoder
and logs why it stopped (#12).
"""

from __future__ import annotations

import re

import anyio
from fastapi import Request

from .audio.encoder import Mp3StreamEncoder
from .backends.base import InvalidOption, VoiceBackend
from .client_identity import Identity, Tier
from .config import Settings, get_settings
from .limits import Overloaded, admit
from .logging_config import get_logger
from .mem import trim_heap
from .quota import QuotaExceeded, quota

log = get_logger("stream")

# Split into sentences, keeping the terminator with its sentence.
_SENTENCE = re.compile(r"[^.!?…\n]+[.!?…\n]*", re.UNICODE)
# Break a clause after ,;: (keeping the mark) when a sentence is too long.
_CLAUSE = re.compile(r"(?<=[,;:])\s+")


def _hard_split(s: str, max_len: int) -> list[str]:
    """Pack whitespace-separated words into <= max_len chunks; char-split any single
    token longer than max_len."""
    out: list[str] = []
    buf = ""
    for word in s.split():
        if len(word) > max_len:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(word[i : i + max_len] for i in range(0, len(word), max_len))
            continue
        if not buf:
            buf = word
        elif len(buf) + 1 + len(word) <= max_len:
            buf += " " + word
        else:
            out.append(buf)
            buf = word
    if buf:
        out.append(buf)
    return out


def _split_long(s: str, max_len: int) -> list[str]:
    """Split an over-long sentence on clause punctuation first, then whitespace."""
    out: list[str] = []
    for clause in _CLAUSE.split(s):
        clause = clause.strip()
        if not clause:
            continue
        if len(clause) <= max_len:
            out.append(clause)
        else:
            out.extend(_hard_split(clause, max_len))
    return out


def sentence_split(text: str, max_len: int = 400) -> list[str]:
    """Deterministically split `text` into synth-sized chunks, each <= max_len."""
    text = text.strip()
    if not text:
        return []
    pieces: list[str] = []
    for match in _SENTENCE.findall(text):
        sentence = match.strip()
        if not sentence:
            continue
        if len(sentence) <= max_len:
            pieces.append(sentence)
        else:
            pieces.extend(_split_long(sentence, max_len))
    # Pack adjacent pieces up to max_len so we don't synth tiny fragments, while
    # keeping chunks small enough for responsive streaming + disconnect.
    packed: list[str] = []
    buf = ""
    for piece in pieces:
        if not buf:
            buf = piece
        elif len(buf) + 1 + len(piece) <= max_len:
            buf += " " + piece
        else:
            packed.append(buf)
            buf = piece
    if buf:
        packed.append(buf)
    return packed


async def synth_stream(
    *,
    backend: VoiceBackend,
    voice: str,
    chunks: list[str],
    ident: Identity,
    request: Request,
    options: dict,
    settings: Settings | None = None,
):
    """Yield one continuous MP3 stream, sentence by sentence. See module docstring."""
    settings = settings or get_settings()
    anon = ident.tier is Tier.ANON
    encoder: Mp3StreamEncoder | None = None
    streamed_chars = 0
    reason = "done"
    try:
        for chunk in chunks:
            if await request.is_disconnected():
                reason = "disconnect"
                break
            # Reserve this chunk's cost right before synth (commit-as-you-yield):
            # out of budget -> stop the stream cleanly, no partial charge for work
            # not done.
            if anon:
                try:
                    await anyio.to_thread.run_sync(quota.reserve_chars, ident.ip, len(chunk), settings)
                except QuotaExceeded:
                    reason = "budget"
                    break
            try:
                async with admit(ident.ip, settings):
                    result = await anyio.to_thread.run_sync(
                        backend.synthesize, chunk, voice, 1.0, options
                    )
            except (Overloaded, InvalidOption) as exc:
                # Mid-stream overload or a bad option: refund this chunk and end the
                # stream cleanly (never a 500 once bytes are flowing).
                if anon:
                    await anyio.to_thread.run_sync(quota.refund_chars, ident.ip, len(chunk))
                reason = "overloaded" if isinstance(exc, Overloaded) else "invalid_option"
                break
            if encoder is None:
                encoder = Mp3StreamEncoder(result.sample_rate)
            data = await anyio.to_thread.run_sync(encoder.encode_pcm, result.pcm)
            if data:
                yield data
            streamed_chars += len(chunk)
        if encoder is not None:
            tail = await anyio.to_thread.run_sync(encoder.close)
            if tail:
                yield tail
    finally:
        # Close the container on every exit — including GeneratorExit when the
        # client disconnects mid-stream (#12) — so no encoder is left open.
        if encoder is not None:
            try:
                encoder.close()
            except Exception:  # noqa: BLE001 — teardown must not raise
                pass
        log.info(
            "stream ip=%s tier=%s chunks=%d chars=%d reason=%s",
            ident.ip, ident.tier.value, len(chunks), streamed_chars, reason,
        )
        # A stream churns per-chunk synth buffers through glibc's arenas and leaves the
        # worker at a multi-GB high-water it never returns on its own. Trim here (a fast,
        # synchronous C call — awaiting is illegal during a disconnect's GeneratorExit) so
        # idle memory goes back to the OS instead of sitting in swap on this small box.
        trim_heap()
