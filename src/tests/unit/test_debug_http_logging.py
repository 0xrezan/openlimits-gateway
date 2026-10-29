from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from src.core.context import RequestContext
from src.observability.debug_http_logging import (
    DebugHTTPLogger,
    build_body_log,
    is_streaming_response,
    sanitize_headers,
)
from src.settings import Settings
from src.tests.fixtures.fakes import make_route_resolution


@dataclass
class RecordingLogger:
    events: list[tuple[str, str, dict[str, object]]] = field(default_factory=list)

    def info(self, event: str, **fields: object) -> None:
        self.events.append(("info", event, fields))

    def error(self, event: str, **fields: object) -> None:
        self.events.append(("error", event, fields))


def make_settings() -> Settings:
    return Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://user:pass@localhost:5432/db",
            "redis_url": "redis://localhost:6379/0",
            "upstream_base_url": "https://main.internal",
            "upstream_service_token": "svc-token",
            "upstream_signing_key": "signing-key",
            "enable_debug_http_logs": True,
            "debug_http_log_max_request_body_bytes": 1024,
            "debug_http_log_max_response_body_bytes": 1024,
            "debug_http_log_max_stream_chunk_previews": 2,
        }
    )


def test_sanitize_headers_redacts_sensitive_values() -> None:
    headers = sanitize_headers(
        {
            "Authorization": "Bearer super-secret-token",
            "X-API-Key": "gk_demo_secret",
            "Content-Type": "application/json",
        }
    )
    assert headers["authorization"] == "Bearer ***redacted***"
    assert headers["x-api-key"] == "gk_***redacted***"
    assert headers["content-type"] == "application/json"


def test_build_body_log_parses_json_and_redacts_sensitive_fields() -> None:
    body = (
        b'{"model":"gpt-5","messages":[{"role":"user","content":"hi"}],'
        b'"api_key":"sk-secret","nested":{"password":"hunter2"}}'
    )
    body_log = build_body_log(
        body,
        content_type="application/json",
        max_bytes=2048,
    )
    assert body_log["model"] == "gpt-5"
    assert body_log["body_truncated"] is False
    assert body_log["body_json"]["api_key"] == "sk-***redacted***"
    assert body_log["body_json"]["nested"]["password"] == "***redacted***"


def test_is_streaming_response_detects_sse() -> None:
    assert is_streaming_response({"content-type": "text/event-stream"}) is True
    assert is_streaming_response({"content-type": "application/json"}) is False


async def test_stream_observer_logs_completion_metadata() -> None:
    recording_logger = RecordingLogger()
    debug_logger = DebugHTTPLogger(make_settings(), logger=recording_logger)
    context = RequestContext(
        request_id="req-123",
        consumer_id=uuid4(),
        consumer_name="alice",
        key_id=uuid4(),
        key_name="default",
        key_prefix="demo",
        route_code="default-api",
        route_id="default-api",
        client_host="127.0.0.1",
    )
    route_resolution = make_route_resolution()
    observer = debug_logger.create_stream_observer(
        context=context,
        route_resolution=route_resolution,
        upstream_url="https://main.internal/api/test",
        status_code=200,
        request_started_at=context.started_at,
        response_started_at=context.started_at,
        retry_count=0,
        response_headers={"content-type": "text/event-stream"},
        content_type="text/event-stream",
    )
    assert observer is not None

    await observer.on_chunk(b"data: hello\\n\\n")
    await observer.on_chunk(b"data: world\\n\\n")
    await observer.on_complete()

    level, event, payload = recording_logger.events[-1]
    assert level == "info"
    assert event == "relay_response_sent"
    assert payload["stream_mode"] is True
    assert payload["stream_total_bytes"] == len(b"data: hello\\n\\n") + len(b"data: world\\n\\n")
    assert payload["stream_chunk_previews"] == ["data: hello\\n\\n", "data: world\\n\\n"]
