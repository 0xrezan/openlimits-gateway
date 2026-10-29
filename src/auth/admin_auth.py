from __future__ import annotations

from typing import Annotated, cast

from fastapi import Header, Request

from src.auth.hashing import verify_api_key
from src.core.exceptions import AdminAuthenticationError
from src.security.ip_allowlist import ip_allowed
from src.settings import Settings


def get_settings_from_request(request: Request) -> Settings:
    return cast(Settings, request.app.state.container.settings)


async def require_admin_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    settings = get_settings_from_request(request)
    if not settings.admin_api_enabled:
        raise AdminAuthenticationError("admin api is disabled")
    client_host = request.client.host if request.client else None
    if not ip_allowed(client_host, settings.admin_api_ip_allowlist):
        raise AdminAuthenticationError("admin client ip not allowed")
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise AdminAuthenticationError()
    token = authorization.split(" ", 1)[1].strip()
    token_hash = settings.admin_api_token_hash
    if token_hash is None or not verify_api_key(token, token_hash):
        raise AdminAuthenticationError()
