"""API-key authentication via `Authorization: Bearer <key>`."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings


bearer_auth = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    bearerFormat="API key",
    description="API key cấu hình trong biến môi trường API_KEYS.",
)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"message": message, "type": "invalid_request_error", "code": "invalid_api_key"},
    )


def require_api_key(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_auth),
    ],
    settings: Settings = Depends(get_settings),
) -> str:
    """FastAPI dependency: validate the bearer token, return it, or raise 401."""
    if credentials is None or credentials.scheme != "Bearer":
        raise _unauthorized("Missing bearer token in Authorization header.")
    token = credentials.credentials.strip()
    if token not in settings.api_key_set:
        raise _unauthorized("Invalid API key provided.")
    return token
