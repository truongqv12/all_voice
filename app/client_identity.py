"""Client identity + tier resolution for the anonymous (no-key) access gate.

Two jobs:

- `client_ip(request)` — the trusted client IP used as the rate/budget key. Behind
  Cloudflare Tunnel the real client IP arrives in the `CF-Connecting-IP` header and
  the socket peer is always `127.0.0.1` (nginx -> localhost API). We therefore
  trust that header **only when the socket peer is loopback** (the mandatory
  loopback-gate, #1): a request that reaches the API from anywhere else (a
  misconfigured bind, a LAN attacker) can't spoof its IP to dodge the budget — its
  header is ignored and its real socket IP is used. The IP is normalised (IPv6 ->
  /64, IPv4 -> /32) so address rotation inside one allocation can't sidestep the
  daily budget (#9).

- `resolve_tier(request, credentials, settings)` — a FastAPI dependency returning
  an `Identity(ip, tier)`. A valid API key is `TRUSTED` (bypasses rate/budget); no
  key with `anon_enabled` is `ANON`; no key with anon disabled is 401 (the old
  key-only behaviour).
"""

from __future__ import annotations

import enum
import ipaddress
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from .auth import _unauthorized, bearer_auth
from .config import Settings, get_settings


class Tier(enum.Enum):
    ANON = "anon"
    TRUSTED = "trusted"


@dataclass(frozen=True)
class Identity:
    ip: str
    tier: Tier


def _normalize_ip(raw: str, ipv6_prefix: int) -> str:
    """Collapse an IP to its budget key: IPv6 -> its /<prefix> network, IPv4 -> as
    is. A non-IP string (e.g. Starlette's `testclient`) passes through unchanged so
    it can still serve as a stable dict key in tests."""
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return raw
    if addr.version == 6:
        net = ipaddress.ip_network(f"{addr}/{ipv6_prefix}", strict=False)
        return str(net.network_address)
    return str(addr)


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def client_ip(request: Request, settings: Settings | None = None) -> str:
    """Resolve the trusted client IP (see module docstring). Loopback-gated: the
    `CF-Connecting-IP` header is honoured only when the socket peer is loopback."""
    settings = settings or get_settings()
    peer = request.client.host if request.client else None
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded and _is_loopback(peer):
        # Trust the edge-provided IP only when the request actually came in over
        # loopback (i.e. from nginx). Take the first hop if a list slipped in.
        raw = forwarded.split(",")[0].strip()
    else:
        raw = peer or "unknown"
    return _normalize_ip(raw, settings.ip_key_ipv6_prefix)


def resolve_tier(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_auth)],
    settings: Settings = Depends(get_settings),
) -> Identity:
    """FastAPI dependency: classify the caller into an access tier.

    Valid key -> TRUSTED. No/invalid key + anon enabled -> ANON. No key + anon
    disabled -> 401 (reuses the auth module's OpenAI 401 envelope)."""
    ip = client_ip(request, settings)
    if (
        credentials is not None
        and credentials.scheme == "Bearer"
        and credentials.credentials.strip() in settings.api_key_set
    ):
        return Identity(ip=ip, tier=Tier.TRUSTED)
    if settings.anon_enabled:
        return Identity(ip=ip, tier=Tier.ANON)
    raise _unauthorized("Missing or invalid API key, and anonymous access is disabled.")
