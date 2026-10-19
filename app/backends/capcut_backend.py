"""CapCut Cloud TTS adapter (Vietnamese presets) — port from capcut-tts-api.

Preset synthesis for 24 Vietnamese (vi-VN) voices via CapCut's Desktop API.
Requests are signed with MD5 headers and RSA PKCS#1 v1.5 payload signatures.
Generated MP3 audio is downloaded from CapCut CDN and decoded in-memory via PyAV
to mono float32 PCM for complete compatibility with the shared audio encoder.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import random
import secrets
import threading
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import av
import numpy as np
import requests

from .base import AudioResult, InvalidOption, Voice, VoiceBackend

logger = logging.getLogger(__name__)

# --- Default device profile ---
DEFAULT_DEVICE: dict[str, Any] = {
    "aid": "359289",
    "app_name": "CapCut",
    "appvr": "8.7.0",
    "version_name": "8.7.0",
    "version_code": "8.7.0",
    "channel": "capcutpc_google",
    "device_platform": "mac",
    "device_type": "MacBookPro17,4",
    "device_brand": "MacBookPro17,4",
    "os_version": "15.7.4",
    "device_id": "73294829104829182746",
    "iid": "73294829104829182746",
    "region": "VN",
    "loc": "VN",
    "lan": "vi-VN",
    "pf": "3",
    "tdid": "73294829104829182746",
}

# --- CapCut RSA Public Key for TTS SSML signing ---
TTS_SIGN_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmTd34Lw4b7IuldSXh/zY
CMla+ITdGG5TeWz6ad+OySd4r+IrY45AoqrYUxhQ2dl+7z+i7r/5vEa8rr39BYfB
8AGMQLmZA8HmgpWBsqrn/V6daUALkKnkLb70Fn32CJigIuGXAYqxUdGuI340aC+0
v5Es3puJsHyzf01/AelE4Cdc6bZhQrASJLBh8R3BQToYClmDVSDUQk28o8sl/guA
Z4n303Vj+6Siv1HayPCdV6kpVVnMBAG4+umUbwGmn132N3fgpzLarFF3XyWmS1zh
D/J07iM/rP8GDO9IskHNHd2phrO0G6KzrcFAnTBHjVv+hCBEfzN/no3FNA9AuC36
mwIDAQAB
-----END PUBLIC KEY-----"""


# --- Signing & Crypto Helpers ---

def compact_json(obj: Any) -> str:
    """Format python object into compact JSON string without whitespace."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def make_x_ss_stub(body_text: str) -> str:
    """Generate x-ss-stub header value (MD5 of request body)."""
    return hashlib.md5(body_text.encode("utf-8")).hexdigest()


def make_trace_id() -> str:
    """Generate unique W3C trace parent header ID."""
    seed = uuid.uuid4().hex[:32]
    return f"00-{seed}-{seed[:16]}-01"


def escape_xml(text: str) -> str:
    """Escape special XML characters for SSML generation."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _der_len(data: bytes, pos: int) -> tuple[int, int]:
    first = data[pos]
    pos += 1
    if first < 0x80:
        return first, pos
    nbytes = first & 0x7F
    return int.from_bytes(data[pos : pos + nbytes], "big"), pos + nbytes


def _der_value(data: bytes, pos: int, tag: int) -> tuple[bytes, int]:
    if data[pos] != tag:
        raise ValueError(f"Bad DER tag: expected 0x{tag:02x}, got 0x{data[pos]:02x}")
    length, pos = _der_len(data, pos + 1)
    return data[pos : pos + length], pos + length


def _der_int(data: bytes, pos: int) -> tuple[int, int]:
    raw, pos = _der_value(data, pos, 0x02)
    return int.from_bytes(raw.lstrip(b"\x00"), "big"), pos


def rsa_public_numbers_from_pem(pem: str) -> tuple[int, int]:
    """Parse RSA modulus and exponent numbers from PEM formatted public key."""
    b64 = "".join(line for line in pem.splitlines() if not line.startswith("-----"))
    der = base64.b64decode(b64)
    outer, pos = _der_value(der, 0, 0x30)
    if pos != len(der):
        raise ValueError("Trailing data in public key")
    _, pos = _der_value(outer, 0, 0x30)
    bit_string, pos = _der_value(outer, pos, 0x03)
    if pos != len(outer) or not bit_string or bit_string[0] != 0:
        raise ValueError("Bad subjectPublicKeyInfo")
    rsa_seq, pos = _der_value(bit_string[1:], 0, 0x30)
    if pos != len(bit_string[1:]):
        raise ValueError("Trailing data in RSA public key")
    modulus, pos = _der_int(rsa_seq, 0)
    exponent, pos = _der_int(rsa_seq, pos)
    if pos != len(rsa_seq):
        raise ValueError("Trailing integer data in RSA public key")
    return modulus, exponent


def rsa_encrypt_pkcs1v15(message: str | bytes, pem: str = TTS_SIGN_PUBLIC_KEY_PEM) -> str:
    """Encrypt message using RSA PKCS#1 v1.5 with standard library cryptography logic."""
    modulus, exponent = rsa_public_numbers_from_pem(pem)
    key_len = (modulus.bit_length() + 7) // 8
    msg = message.encode("utf-8") if isinstance(message, str) else bytes(message)
    if len(msg) > key_len - 11:
        raise ValueError("Message too long for RSA PKCS#1 v1.5 padding")
    ps_len = key_len - len(msg) - 3
    ps = bytearray()
    while len(ps) < ps_len:
        chunk = secrets.token_bytes(ps_len - len(ps))
        ps.extend(b for b in chunk if b != 0)
    encoded = b"\x00\x02" + bytes(ps[:ps_len]) + b"\x00" + msg
    encrypted = pow(int.from_bytes(encoded, "big"), exponent, modulus).to_bytes(key_len, "big")
    return base64.b64encode(encrypted).decode("ascii")


def make_tts_payload_sign(
    ssml: str,
    extra_info: str | None,
    device_id: str,
    app_id: str,
    *,
    pem: str = TTS_SIGN_PUBLIC_KEY_PEM,
) -> str:
    """Build RSA payload signature for CapCut TTS."""
    ssml_md5 = hashlib.md5(ssml.encode("utf-8")).hexdigest()
    sign_input = f"appid:{app_id}&did:{device_id}&creditDisable:false&ssml:{ssml_md5}"
    if extra_info is not None:
        sign_input += f"&extraInfo:{extra_info}"
    return rsa_encrypt_pkcs1v15(sign_input, pem=pem)


def make_sign_header(url: str, appvr: str, device_time: str, tdid: str) -> str:
    """Calculate MD5 HTTP sign header for CapCut common task API."""
    path = url.split("?", 1)[0]
    sign_str = f"9e2c|{path[-7:]}|3|{appvr}|{device_time}|{tdid}|11ac"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def common_query(device: dict[str, Any], babi_param: Any = None, include_region: bool = True) -> dict[str, str]:
    """Build standard query parameter dict for CapCut API calls."""
    q = {
        "app_name": str(device["app_name"]),
        "device_type": str(device["device_type"]),
        "os_version": str(device["os_version"]),
        "channel": str(device["channel"]),
        "version_name": str(device["version_name"]),
        "device_brand": str(device["device_brand"]),
        "device_id": str(device["device_id"]),
        "iid": str(device["iid"]),
        "version_code": str(device["version_code"]),
        "device_platform": str(device["device_platform"]),
        "aid": str(device["aid"]),
    }
    if include_region:
        q["region"] = str(device["region"])
    if babi_param is not None:
        q["babi_param"] = compact_json(babi_param)
    return q


def base_headers(device: dict[str, Any], body_text: str, appid: bool = False) -> dict[str, str]:
    """Build base HTTP headers required by CapCut API endpoints."""
    now = str(int(time.time()))
    headers = {
        "content-type": "application/json",
        "appvr": str(device["appvr"]),
        "ch": str(device["channel"]),
        "device-time": now,
        "lan": str(device["lan"]),
        "loc": str(device["loc"]),
        "pf": str(device["pf"]),
        "sign-ver": "1",
        "tdid": str(device["tdid"]),
        "x-ss-stub": make_x_ss_stub(body_text),
        "x-ss-dp": str(device["aid"]),
        "x-khronos": now,
        "x-tt-trace-id": make_trace_id(),
        "user-agent": "Cronet/TTNetVersion:1d7cc3b1 2025-07-16 QuicVersion:52c2b40d 2025-04-03",
        "accept-encoding": "gzip, deflate",
        "store-country-code": str(device["loc"]).lower(),
        "store-country-code-src": "did",
        "is-dispatch-us-ttp": "0",
        "is-app-region-us-ttp": "0",
    }
    if appid:
        headers["app-sdk-version"] = str(device["appvr"])
        headers["appid"] = str(device["aid"])
    return headers


def _task_status_succeeded(status: Any) -> bool:
    return str(status or "").lower() in {"success", "succeed", "succeeded", "completed", "done"}


def _checked_json_response(resp: Any, label: str) -> dict[str, Any]:
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(
            f"{label} returned non-JSON HTTP {resp.status_code}: {resp.text[:500]}"
        ) from exc
    if resp.status_code >= 400:
        raise RuntimeError(f"{label} HTTP {resp.status_code}: {data}")
    ret = data.get("ret") if isinstance(data, dict) else None
    if ret not in (None, 0, "0", ""):
        raise RuntimeError(f"{label} API error ret={ret!r}: {data.get('errmsg', '')}")
    return data


_OPUS_SAFE_RATES = (8000, 12000, 16000, 24000, 48000)


def _apply_atempo_f32(pcm: np.ndarray, sample_rate: int, speed: float) -> np.ndarray:
    """Apply FFmpeg pitch-preserving WSOLA time-scale (atempo) to mono float32 PCM."""
    speed_val = max(0.25, min(4.0, float(speed)))
    if abs(speed_val - 1.0) <= 1e-3 or len(pcm) == 0:
        return pcm

    graph = av.filter.Graph()
    src = graph.add(
        "abuffer",
        f"time_base=1/{sample_rate}:sample_rate={sample_rate}:sample_fmt=fltp:channel_layout=mono",
    )
    last = src
    rem = speed_val
    while rem < 0.5:
        node = graph.add("atempo", "0.5")
        last.link_to(node)
        last = node
        rem /= 0.5
    node = graph.add("atempo", f"{rem:.4f}")
    last.link_to(node)
    last = node

    fmt = graph.add("aformat", f"sample_fmts=fltp:channel_layouts=mono:sample_rates={sample_rate}")
    last.link_to(fmt)
    sink = graph.add("abuffersink")
    fmt.link_to(sink)
    graph.configure()

    in_frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="fltp", layout="mono")
    in_frame.sample_rate = sample_rate
    in_frame.pts = 0

    out_frames: list[np.ndarray] = []
    src.push(in_frame)
    src.push(None)
    while True:
        try:
            f = sink.pull()
            out_frames.append(f.to_ndarray().reshape(-1))
        except (av.BlockingIOError, av.EOFError):
            break

    if not out_frames:
        return pcm
    stretched = np.concatenate(out_frames).astype(np.float32, copy=False)
    return np.clip(stretched, -1.0, 1.0)


def _decode_mp3_bytes(audio_bytes: bytes, speed: float = 1.0) -> tuple[np.ndarray, int]:
    """Decode in-memory MP3 bytes to mono float32 PCM and Opus-safe sample rate using PyAV."""
    if not audio_bytes:
        raise RuntimeError("Empty audio bytes received from CapCut CDN")
    try:
        container = av.open(io.BytesIO(audio_bytes), format="mp3")
    except Exception as exc:
        raise RuntimeError(f"Invalid MP3 data from CapCut CDN: {exc}") from exc
    try:
        if not container.streams.audio:
            raise RuntimeError("No audio stream found in MP3 payload")
        stream = container.streams.audio[0]
        raw_rate = int(stream.rate or 0)
        target_rate = raw_rate if raw_rate in _OPUS_SAFE_RATES else 24000
        resampler: av.AudioResampler | None = (
            av.AudioResampler(format="fltp", layout="mono", rate=target_rate)
            if raw_rate > 0
            else None
        )
        frames: list[np.ndarray] = []
        for frame in container.decode(stream):
            if resampler is None:
                f_rate = int(frame.sample_rate or 24000)
                target_rate = f_rate if f_rate in _OPUS_SAFE_RATES else 24000
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=target_rate)
            for rframe in resampler.resample(frame):
                frames.append(rframe.to_ndarray().reshape(-1))
        if resampler is not None:
            for rframe in resampler.resample(None):
                frames.append(rframe.to_ndarray().reshape(-1))
    finally:
        container.close()

    if not frames or target_rate <= 0:
        raise RuntimeError("No audio frames decoded from CapCut MP3 response")

    pcm = np.concatenate(frames).astype(np.float32, copy=False)
    pcm = np.clip(pcm, -1.0, 1.0)
    if abs(float(speed or 1.0) - 1.0) > 1e-3:
        pcm = _apply_atempo_f32(pcm, int(target_rate), float(speed))
    return pcm, int(target_rate)


# --- CapCutBackend Class ---

class CapCutBackend(VoiceBackend):
    name = "capcut"
    supports_cloning = False

    def __init__(self, settings, session: requests.Session | None = None) -> None:
        self._voices_path = getattr(settings, "capcut_voices_path", "app/data/capcut_voices.json")
        self._default_voice = getattr(settings, "capcut_default_voice", "BV421_vivn_streaming")
        self._base_url = getattr(settings, "capcut_base_url", "https://editor-api-sg.capcutapi.com").rstrip("/")
        self._timeout = float(getattr(settings, "capcut_timeout_s", 60.0))
        self._poll_interval = float(getattr(settings, "capcut_poll_interval_s", 1.0))
        self._cookie = getattr(settings, "capcut_cookie", "")
        self._bearer = getattr(settings, "capcut_bearer", "")

        self._injected_session = session
        self._thread_local = threading.local()
        self._catalog_lock = threading.Lock()

        # Randomize device_id per client instance
        rand_id = str(random.randint(10**19, 10**20 - 1))
        self._device = dict(DEFAULT_DEVICE)
        self._device["device_id"] = rand_id
        self._device["iid"] = rand_id
        self._device["tdid"] = rand_id

        self._extra_headers: dict[str, str] = {}
        if self._cookie:
            self._extra_headers["Cookie"] = self._cookie
        if self._bearer:
            auth = self._bearer if self._bearer.lower().startswith("bearer ") else f"Bearer {self._bearer}"
            self._extra_headers["Authorization"] = auth

        self._voices_cache: list[Voice] | None = None
        self._voice_records: dict[str, dict[str, Any]] = {}

    def _get_session(self) -> requests.Session:
        if self._injected_session is not None:
            return self._injected_session
        sess = getattr(self._thread_local, "session", None)
        if sess is None:
            sess = requests.Session()
            self._thread_local.session = sess
        return sess

    @staticmethod
    def is_available(settings) -> bool:
        """True if the Vietnamese voice catalog JSON exists and contains >= 1 voice."""
        if not hasattr(settings, "capcut_voices_path"):
            return False
        path = settings.capcut_voices_path
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return isinstance(data, list) and len(data) > 0
        except Exception:
            return False

    def _load_catalog(self) -> list[Voice]:
        if self._voices_cache is not None:
            return self._voices_cache
        with self._catalog_lock:
            if self._voices_cache is not None:
                return self._voices_cache
            if not os.path.isfile(self._voices_path):
                self._voices_cache = []
                return self._voices_cache

            with open(self._voices_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            voices: list[Voice] = []
            records: dict[str, dict[str, Any]] = {}
            for item in data:
                v_id = str(item["voice_type"]).strip()
                v_name = str(item.get("display_name", v_id)).strip()
                voices.append(
                    Voice(
                        id=v_id,
                        name=v_name,
                        model=self.name,
                        language="vi",
                    )
                )
                records[v_id] = item

            self._voice_records = records
            self._voices_cache = voices
            return self._voices_cache

    def list_voices(self) -> list[Voice]:
        return self._load_catalog()

    def resolve_voice(self, voice: str | None, *, strict: bool = False) -> str | None:
        voices = self.list_voices()
        if not voices:
            raise RuntimeError(f"Backend '{self.name}' exposes no voices")

        if voice and voice.strip():
            voice_clean = voice.strip()
            target = voice_clean.lower()
            # 1. Exact match ID
            for v in voices:
                if v.id == voice_clean:
                    return v.id
            # 2. Case-insensitive ID match
            for v in voices:
                if v.id.lower() == target:
                    return v.id
            # 3. Exact match display name
            for v in voices:
                if v.name.strip() == voice_clean:
                    return v.id
            # 4. Case-insensitive display name match
            for v in voices:
                if v.name.strip().lower() == target:
                    return v.id

        if strict:
            return None

        # Lenient fallback to configured default voice
        for v in voices:
            if v.id == self._default_voice:
                return v.id
        return voices[0].id

    def _get_voice_info(self, voice_id: str) -> tuple[str, str]:
        self._load_catalog()
        item = self._voice_records.get(voice_id)
        if item:
            return item["voice_type"], item["resource_id"]
        # Fallback default (BV421_vivn_streaming resource_id)
        return voice_id, "7252594014782755330"

    def synthesize(
        self, text: str, voice: str, speed: float = 1.0, options: dict | None = None
    ) -> AudioResult:
        if not text or not text.strip():
            raise InvalidOption("Input text must not be empty or whitespace-only")

        resolved_id = self.resolve_voice(voice, strict=False)
        if not resolved_id:
            raise RuntimeError(f"Could not resolve voice for '{voice}'")

        voice_type, resource_id = self._get_voice_info(resolved_id)
        speed_val = float(speed) if speed else 1.0

        # Build SSML
        ssml = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">\n'
            f'    <voice name="{escape_xml(voice_type)}" mock_tone_info="" platform="sami" '
            f'resource_id="{escape_xml(resource_id)}" emotion="" emotion_scale="0" style="" role="" '
            f'moyin_emotion="" is_clone_tone="false" need_subtitle_timestamp="false">\n'
            f'        <prosody rate="{speed_val:.2f}">{escape_xml(text)}</prosody>\n'
            '    </voice>\n'
            '</speak>'
        )

        babi = {
            "feature_entrance": "editor",
            "feature_entrance_detail": "editor-feature-text_to_speech",
            "feature_key": "text_to_speech",
            "scenario": "video_editor",
        }
        extra_info = compact_json({"benefit_info": {}})
        payload = {
            "audio_format": "mp3",
            "babi_param": compact_json(babi),
            "credit_disable": False,
            "extra_info": extra_info,
            "need_merge_voice": False,
            "need_subtitle_timestamp": False,
            "scene": "text_to_speech",
            "ssml": ssml,
            "sign": make_tts_payload_sign(
                ssml, extra_info, self._device["device_id"], self._device["aid"]
            ),
        }
        body = {
            "bind_id": str(uuid.uuid4()),
            "can_queue": True,
            "enter_from": "text_to_speech",
            "tasks": [
                {
                    "context": str(uuid.uuid4()),
                    "payload": compact_json(payload),
                    "req_key": "sami_text_to_speech",
                    "task_version": "v3",
                }
            ],
        }

        session = self._get_session()
        deadline = time.monotonic() + self._timeout

        body_text = compact_json(body)
        path = "/lv/v1/common_task/new"
        query = common_query(self._device, babi, include_region=True)
        url = self._base_url + path + "?" + urlencode(query)
        headers = base_headers(self._device, body_text, appid=True)
        headers.update(self._extra_headers)
        headers["sign"] = make_sign_header(
            url, self._device["appvr"], headers["device-time"], self._device["tdid"]
        )

        req_timeout = max(0.5, min(self._timeout, deadline - time.monotonic()))
        resp = session.post(
            url,
            headers=headers,
            data=body_text.encode("utf-8"),
            timeout=req_timeout,
            allow_redirects=False,
        )
        create_res = _checked_json_response(resp, "create_tts_task")

        tasks = (create_res.get("data") or {}).get("tasks") or []
        if not tasks:
            raise RuntimeError(f"No task returned from CapCut TTS API: {create_res}")

        task_id = tasks[0]["id"]
        token = tasks[0]["token"]
        bind_id = tasks[0].get("bind_id") or (create_res.get("data") or {}).get("bind_id") or ""

        # Poll for completion within remaining deadline
        final_query_res = None
        while time.monotonic() < deadline:
            q_body = {
                "tasks": [
                    {
                        "bind_id": bind_id,
                        "id": task_id,
                        "req_key": "sami_text_to_speech",
                        "task_version": "v3",
                        "token": token,
                    }
                ]
            }
            q_body_text = compact_json(q_body)
            q_path = "/lv/v1/common_task/query"
            q_query = common_query(self._device, None, include_region=False)
            q_url = self._base_url + q_path + "?" + urlencode(q_query)
            q_headers = base_headers(self._device, q_body_text, appid=True)
            q_headers.update(self._extra_headers)
            q_headers["sign"] = make_sign_header(
                q_url, self._device["appvr"], q_headers["device-time"], self._device["tdid"]
            )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            q_resp = session.post(
                q_url,
                headers=q_headers,
                data=q_body_text.encode("utf-8"),
                timeout=max(0.5, min(15.0, remaining)),
                allow_redirects=False,
            )
            query_res = _checked_json_response(q_resp, "query_tts_task")
            q_tasks = (query_res.get("data") or {}).get("tasks") or []
            if q_tasks:
                status = q_tasks[0].get("status")
                if _task_status_succeeded(status):
                    final_query_res = query_res
                    break
                if str(status).lower() == "failed":
                    raise RuntimeError(f"CapCut TTS Task failed: {query_res}")

            remaining_after_poll = deadline - time.monotonic()
            if remaining_after_poll <= 0:
                break
            time.sleep(min(self._poll_interval, remaining_after_poll))

        if final_query_res is None:
            raise RuntimeError(f"CapCut TTS Task timed out after {self._timeout}s")

        # Extract audio URL
        q_tasks = (final_query_res.get("data") or {}).get("tasks") or []
        raw_payload = q_tasks[0].get("payload", {})
        if isinstance(raw_payload, str):
            try:
                payload_dict = json.loads(raw_payload)
            except Exception as exc:
                raise RuntimeError(f"Failed to parse CapCut task payload: {exc}") from exc
        else:
            payload_dict = raw_payload

        subtitles = (payload_dict or {}).get("audio_subtitles") or []
        if not subtitles:
            raise RuntimeError(f"CapCut TTS task succeeded but returned no audio_subtitles: {final_query_res}")

        audio_item = subtitles[0]
        audio_url = audio_item.get("speech_url") or audio_item.get("audio_url") or audio_item.get("url")
        if not isinstance(audio_url, str) or not audio_url.startswith(("http://", "https://")):
            raise RuntimeError(f"No valid download URL found in CapCut audio subtitle: {audio_item}")

        # Download MP3 audio
        dl_timeout = max(0.5, min(self._timeout, deadline - time.monotonic()))
        dl_resp = session.get(audio_url, timeout=dl_timeout)
        if dl_resp.status_code >= 400:
            raise RuntimeError(f"Failed to download audio from CapCut CDN (HTTP {dl_resp.status_code})")

        pcm, sample_rate = _decode_mp3_bytes(dl_resp.content, speed=speed_val)
        return AudioResult(pcm=pcm, sample_rate=sample_rate)
