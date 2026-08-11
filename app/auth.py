"""API-key authentication via `Authorization: Bearer <key>`."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"message": message, "type": "invalid_request_error", "code": "invalid_api_key"},
    )


def require_api_key(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """FastAPI dependency: validate the bearer token, return it, or raise 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized("Missing bearer token in Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    if token not in settings.api_key_set:
        raise _unauthorized("Invalid API key provided.")
    return token
