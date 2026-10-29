from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.app_factory import create_app
from src.core.exceptions import AuthenticationError, BodyTooLargeError, RateLimitExceededError
from src.middleware.auth import AuthMiddleware
from src.middleware.error_mapper import GatewayErrorMiddleware, register_exception_handlers
from src.settings import Settings


def _app_raising(exc: Exception) -> FastAPI:
    class RaisingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
            raise exc

    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RaisingMiddleware)
    app.add_middleware(GatewayErrorMiddleware)

    @app.get("/api/echo")
    async def echo() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (AuthenticationError(), 401, "authentication_failed"),
        (BodyTooLargeError(), 413, "request_body_too_large"),
        (RateLimitExceededError(retry_after_seconds=7), 429, "rate_limit_exceeded"),
    ],
)
def test_middleware_errors_keep_their_status(exc: Exception, status: int, code: str) -> None:
    response = TestClient(_app_raising(exc), raise_server_exceptions=False).get("/api/echo")

    assert response.status_code == status
    assert response.json()["code"] == code


def test_rate_limit_error_keeps_retry_after_header() -> None:
    app = _app_raising(RateLimitExceededError(retry_after_seconds=7))
    response = TestClient(app, raise_server_exceptions=False).get("/api/echo")

    assert response.headers["retry-after"] == "7"


def test_create_app_maps_errors_outside_auth_and_limits() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://user:pass@localhost:5432/db",
            "redis_url": "redis://localhost:6379/0",
            "upstream_base_url": "https://main.internal",
            "upstream_service_token": "svc-token",
            "upstream_signing_enabled": False,
        }
    )
    # user_middleware is ordered outermost first.
    order = [m.cls for m in create_app(settings).user_middleware]

    assert order.index(GatewayErrorMiddleware) < order.index(AuthMiddleware)
