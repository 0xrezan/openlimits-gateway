from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import httpx
import pytest
import respx

from src.auth.service_identity import build_upstream_identity_headers
from src.core.context import RequestContext
from src.observability.debug_http_logging import DebugHTTPLogger
from src.observability.metrics import GatewayMetrics
from src.proxy.bulkhead import BulkheadRegistry
from src.proxy.circuit_breaker import CircuitBreakerRegistry
from src.proxy.relay import RelayService
from src.settings import Settings
from src.tests.fixtures.fakes import make_route_resolution


@pytest.mark.asyncio
@respx.mock
async def test_relay_service_forwards_request() -> None:
    respx.get("https://main.internal/api/test").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "application/json"}, json={"ok": True}
        )
    )
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://user:pass@localhost:5432/db",
            "redis_url": "redis://localhost:6379/0",
            "upstream_base_url": "https://main.internal",
            "upstream_service_token": "svc-token",
            "upstream_signing_key": "signing-key",
        }
    )
    client = httpx.AsyncClient(base_url=settings.upstream_base_url)
    relay = RelayService(
        client=client,
        settings=settings,
        metrics=GatewayMetrics(),
        debug_logger=DebugHTTPLogger(settings),
        circuit_breakers=CircuitBreakerRegistry(),
        bulkheads=BulkheadRegistry(),
    )
    request = httpx.Request("GET", "https://gateway.local/api/test")

    @dataclass
    class DummyFastAPIRequest:
        method: str = "GET"
        url: httpx.URL = request.url
        headers: dict[str, str] = field(default_factory=dict)
        query_params: dict[str, str] = field(default_factory=dict)

        async def body(self) -> bytes:
            return b""

    result = await relay.relay(
        request=DummyFastAPIRequest(),  # type: ignore[arg-type]
        route_resolution=make_route_resolution(),
        context=RequestContext(
            request_id="req-1",
            consumer_id=uuid4(),
            consumer_name="alice",
            key_id=uuid4(),
            key_name="default",
            key_prefix="demo",
            route_code="default-api",
            route_id="default-api",
            client_host="127.0.0.1",
        ),
        allowed_headers=["accept", "content-type"],
        identity_headers={},
        body=b"",
    )
    assert result.status_code == 200
    await client.aclose()


def test_service_identity_includes_request_id() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://user:pass@localhost:5432/db",
            "redis_url": "redis://localhost:6379/0",
            "upstream_base_url": "https://main.internal",
            "upstream_service_token": "svc-token",
            "upstream_signing_key": "signing-key",
        }
    )
    headers = build_upstream_identity_headers(
        settings=settings,
        context=RequestContext(request_id="req-123"),
        method="POST",
        path_with_query="/api/test",
        body=b'{"ok":true}',
    )
    assert headers["x-request-id"] == "req-123"
