from __future__ import annotations

import json
import socket
import ssl
from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import parse_qs

import httpx
import structlog
from fastapi import Request

from src.security.redaction import (
    is_sensitive_key,
    mask_secret_text,
    redact_mapping,
    redact_text_preview,
)

if TYPE_CHECKING:
    from src.auth.key_service import AuthenticatedPrincipal
    from src.core.context import RequestContext
    from src.routes.registry import RouteResolution
    from src.settings import Settings


class StructuredLogger(Protocol):
    def info(self, event: str, **fields: Any) -> Any: ...

    def error(self, event: str, **fields: Any) -> Any: ...


JSON_CONTENT_TYPE_MARKERS = (
    "application/json",
    "application/problem+json",
    "application/vnd.api+json",
    "+json",
)
TEXTUAL_CONTENT_TYPE_PREFIXES = (
    "application/json",
    "application/problem+json",
    "application/vnd.api+json",
    "application/xml",
    "application/x-www-form-urlencoded",
    "application/graphql",
    "text/",
)
STREAMING_CONTENT_TYPE_PREFIXES = (
    "text/event-stream",
    "application/x-ndjson",
)


def _lower_headers(headers: httpx.Headers | dict[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in dict(headers).items()}


def serialize_query_params(query_string: str) -> dict[str, list[str]]:
    return parse_qs(query_string, keep_blank_values=True)


def url_query_string(url: httpx.URL) -> str:
    query = url.query
    if isinstance(query, bytes):
        return query.decode("utf-8")
    return str(query)


def sanitize_headers(headers: httpx.Headers | dict[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in _lower_headers(headers).items():
        if is_sensitive_key(key):
            sanitized[key] = mask_secret_text(value)
        else:
            sanitized[key] = redact_text_preview(value)
    return sanitized


def is_json_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return False
    lowered = content_type.lower()
    return any(marker in lowered for marker in JSON_CONTENT_TYPE_MARKERS)


def is_textual_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return False
    lowered = content_type.lower()
    return any(
        lowered.startswith(prefix) or prefix in lowered for prefix in TEXTUAL_CONTENT_TYPE_PREFIXES
    )


def is_streaming_response(headers: httpx.Headers | dict[str, str]) -> bool:
    normalized = _lower_headers(headers)
    content_type = normalized.get("content-type")
    transfer_encoding = normalized.get("transfer-encoding", "").lower()
    if content_type is not None:
        lowered = content_type.lower()
        if any(lowered.startswith(prefix) for prefix in STREAMING_CONTENT_TYPE_PREFIXES):
            return True
    return "chunked" in transfer_encoding


def classify_upstream_error(error: Exception) -> str:
    if isinstance(error, httpx.ConnectTimeout):
        return "connect_timeout"
    if isinstance(error, httpx.ReadTimeout):
        return "read_timeout"
    if isinstance(error, httpx.WriteTimeout):
        return "write_timeout"
    if isinstance(error, httpx.PoolTimeout):
        return "pool_timeout"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"

    cause = error.__cause__
    if isinstance(cause, socket.gaierror):
        return "dns_error"
    if isinstance(cause, ConnectionResetError):
        return "connection_reset"
    if isinstance(cause, EOFError):
        return "upstream_eof"
    if isinstance(cause, ssl.SSLError):
        return "tls_error"

    if isinstance(error, httpx.ConnectError):
        return "connect_error"
    if isinstance(error, httpx.ReadError):
        return "read_error"
    if isinstance(error, httpx.WriteError):
        return "write_error"
    if isinstance(error, httpx.RemoteProtocolError):
        return "remote_protocol_error"
    if isinstance(error, httpx.TransportError):
        return "transport_error"
    return "unexpected_error"


def _decode_preview_bytes(preview: bytes, *, content_type: str | None) -> str:
    if not preview:
        return ""
    if is_textual_content_type(content_type):
        return redact_text_preview(preview.decode("utf-8", errors="replace"))
    return f"<binary payload preview: {len(preview)} bytes>"


def _extract_model(parsed: Any) -> str | None:
    if isinstance(parsed, dict):
        model = parsed.get("model")
        if isinstance(model, str):
            return model
    return None


def build_body_log(
    body: bytes,
    *,
    content_type: str | None,
    max_bytes: int,
    total_length: int | None = None,
) -> dict[str, Any]:
    content_length = total_length if total_length is not None else len(body)
    fields: dict[str, Any] = {
        "content_type": content_type,
        "content_length": content_length,
        "body_logged_bytes": min(len(body), max(max_bytes, 0)),
        "body_truncated": content_length > max(max_bytes, 0),
        "body_present": bool(content_length),
    }
    if not body or max_bytes <= 0:
        return fields

    preview = body[:max_bytes]
    if is_json_content_type(content_type) and content_length <= max_bytes:
        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as error:
            fields["malformed_json"] = True
            fields["body_parse_error"] = error.msg
            fields["body_preview"] = _decode_preview_bytes(preview, content_type=content_type)
        else:
            sanitized = redact_mapping(parsed) if isinstance(parsed, dict) else parsed
            fields["body_json"] = sanitized
            model = _extract_model(parsed)
            if model is not None:
                fields["model"] = model
        return fields

    fields["body_preview"] = _decode_preview_bytes(preview, content_type=content_type)
    return fields


@dataclass(slots=True)
class StreamDebugObserver:
    logger: DebugHTTPLogger
    context: RequestContext
    route_resolution: RouteResolution
    upstream_url: str
    status_code: int
    request_started_at: float
    response_started_at: float
    retry_count: int
    sanitized_response_headers: dict[str, str]
    content_type: str | None
    max_logged_body_bytes: int
    max_chunk_previews: int
    total_bytes: int = 0
    first_chunk_after_headers_ms: float | None = None
    first_chunk_after_request_ms: float | None = None
    preview_buffer: bytearray = field(default_factory=bytearray)
    chunk_previews: list[str] = field(default_factory=list)

    async def on_chunk(self, chunk: bytes) -> None:
        if self.first_chunk_after_headers_ms is None:
            now = monotonic()
            self.first_chunk_after_headers_ms = round((now - self.response_started_at) * 1000, 2)
            self.first_chunk_after_request_ms = round((now - self.request_started_at) * 1000, 2)
        self.total_bytes += len(chunk)
        if len(self.preview_buffer) < self.max_logged_body_bytes:
            remaining = self.max_logged_body_bytes - len(self.preview_buffer)
            self.preview_buffer.extend(chunk[:remaining])
        if len(self.chunk_previews) < self.max_chunk_previews:
            preview_size = min(len(chunk), self.max_logged_body_bytes)
            self.chunk_previews.append(
                _decode_preview_bytes(chunk[:preview_size], content_type=self.content_type)
            )

    async def on_complete(self) -> None:
        response_log = build_body_log(
            bytes(self.preview_buffer),
            content_type=self.content_type,
            max_bytes=self.max_logged_body_bytes,
            total_length=self.total_bytes,
        )
        self.logger.log_relay_response_sent(
            context=self.context,
            route_code=self.route_resolution.route.code,
            upstream_url=self.upstream_url,
            status_code=self.status_code,
            stream_mode=True,
            total_duration_ms=round((monotonic() - self.request_started_at) * 1000, 2),
            retry_count=self.retry_count,
            response_headers=self.sanitized_response_headers,
            stream_total_bytes=self.total_bytes,
            stream_first_chunk_after_headers_ms=self.first_chunk_after_headers_ms,
            stream_first_chunk_after_request_ms=self.first_chunk_after_request_ms,
            stream_chunk_previews=self.chunk_previews,
            **response_log,
        )

    async def on_error(self, error: Exception) -> None:
        self.logger.log_relay_error(
            context=self.context,
            route_code=self.route_resolution.route.code,
            upstream_url=self.upstream_url,
            stage="upstream_response_stream",
            error=error,
            retry_count=self.retry_count,
            extra={
                "status_code": self.status_code,
                "stream_total_bytes": self.total_bytes,
                "stream_first_chunk_after_headers_ms": self.first_chunk_after_headers_ms,
            },
        )


class DebugHTTPLogger:
    def __init__(
        self,
        settings: Settings,
        logger: StructuredLogger | None = None,
    ) -> None:
        self.enabled = settings.enable_debug_http_logs
        self.max_request_body_bytes = settings.debug_http_log_max_request_body_bytes
        self.max_response_body_bytes = settings.debug_http_log_max_response_body_bytes
        self.max_stream_chunk_previews = settings.debug_http_log_max_stream_chunk_previews
        self._logger = logger or structlog.get_logger(__name__)

    def _emit(self, level: str, event: str, **fields: Any) -> None:
        if not self.enabled:
            return
        try:
            log_method = getattr(self._logger, level)
            log_method(event, **fields)
        except Exception:
            return

    @staticmethod
    def _context_fields(context: RequestContext) -> dict[str, Any]:
        return {
            "request_id": context.request_id,
            "consumer_id": str(context.consumer_id) if context.consumer_id else None,
            "consumer_name": context.consumer_name,
            "key_id": str(context.key_id) if context.key_id else None,
            "key_name": context.key_name,
            "key_prefix": context.key_prefix,
            "route_code": context.route_code,
            "route_id": context.route_id,
            "client_host": context.client_host,
        }

    def log_relay_request_received(
        self,
        *,
        request: Request,
        context: RequestContext,
        principal: AuthenticatedPrincipal | None,
        route_resolution: RouteResolution,
        body: bytes,
    ) -> None:
        if not self.enabled:
            return
        headers = sanitize_headers(dict(request.headers))
        body_fields = build_body_log(
            body,
            content_type=headers.get("content-type"),
            max_bytes=self.max_request_body_bytes,
        )
        self._emit(
            "info",
            "relay_request_received",
            **self._context_fields(context),
            consumer_name=principal.consumer_name if principal else context.consumer_name,
            key_prefix=principal.key_prefix if principal else context.key_prefix,
            method=request.method,
            public_path=request.url.path,
            query_string=request.url.query,
            query_params=serialize_query_params(request.url.query),
            sanitized_headers=headers,
            request_streaming=False,
            **body_fields,
        )

    def log_upstream_request_sent(
        self,
        *,
        context: RequestContext,
        route_resolution: RouteResolution,
        upstream_url: str,
        method: str,
        headers: dict[str, str],
        body: bytes,
        preparation_ms: float,
        request_streaming: bool,
    ) -> None:
        if not self.enabled:
            return
        sanitized_headers = sanitize_headers(headers)
        content_type = sanitized_headers.get("content-type")
        body_fields = build_body_log(
            body,
            content_type=content_type,
            max_bytes=self.max_request_body_bytes,
        )
        query_string = url_query_string(httpx.URL(upstream_url))
        self._emit(
            "info",
            "upstream_request_sent",
            **self._context_fields(context),
            upstream_url=upstream_url,
            upstream_path=httpx.URL(upstream_url).path,
            method=method,
            query_string=query_string,
            query_params=serialize_query_params(query_string),
            sanitized_headers=sanitized_headers,
            preparation_ms=preparation_ms,
            request_streaming=request_streaming,
            **body_fields,
        )

    def log_upstream_response_received(
        self,
        *,
        context: RequestContext,
        route_resolution: RouteResolution,
        upstream_url: str,
        response: httpx.Response,
        upstream_duration_ms: float,
        stream_mode: bool,
        retry_count: int,
        body: bytes | None = None,
    ) -> None:
        if not self.enabled:
            return
        sanitized_headers = sanitize_headers(response.headers)
        query_string = url_query_string(response.request.url)
        fields: dict[str, Any] = {
            **self._context_fields(context),
            "upstream_url": upstream_url,
            "upstream_path": response.request.url.path,
            "query_string": query_string,
            "query_params": serialize_query_params(query_string),
            "status_code": response.status_code,
            "sanitized_headers": sanitized_headers,
            "content_type": sanitized_headers.get("content-type"),
            "content_length": response.headers.get("content-length"),
            "stream_mode": stream_mode,
            "retry_count": retry_count,
            "upstream_duration_ms": upstream_duration_ms,
        }
        if body is not None:
            fields.update(
                build_body_log(
                    body,
                    content_type=sanitized_headers.get("content-type"),
                    max_bytes=self.max_response_body_bytes,
                )
            )
        self._emit("info", "upstream_response_received", **fields)

    def log_relay_response_sent(
        self,
        *,
        context: RequestContext,
        route_code: str | None,
        upstream_url: str,
        status_code: int,
        stream_mode: bool,
        total_duration_ms: float,
        retry_count: int,
        response_headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        fields = self._context_fields(context)
        fields["route_code"] = route_code or context.route_code
        self._emit(
            "info",
            "relay_response_sent",
            **fields,
            upstream_url=upstream_url,
            status_code=status_code,
            stream_mode=stream_mode,
            retry_count=retry_count,
            total_duration_ms=total_duration_ms,
            response_headers=response_headers,
            **extra,
        )

    def log_relay_error(
        self,
        *,
        context: RequestContext | None,
        route_code: str | None,
        upstream_url: str | None,
        stage: str,
        error: Exception,
        retry_count: int = 0,
        extra: dict[str, Any] | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "route_code": route_code or (context.route_code if context is not None else None),
            "upstream_url": upstream_url,
            "stage": stage,
            "error_kind": classify_upstream_error(error),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "retry_count": retry_count,
        }
        if context is not None:
            fields.update(self._context_fields(context))
            fields["duration_ms"] = round((monotonic() - context.started_at) * 1000, 2)
        if extra:
            fields.update(extra)
        self._emit("error", "relay_error", **fields)

    def log_upstream_retry(
        self,
        *,
        context: RequestContext,
        route_resolution: RouteResolution,
        upstream_url: str,
        attempt_number: int,
        error: Exception,
        status_code: int | None = None,
    ) -> None:
        self.log_relay_error(
            context=context,
            route_code=route_resolution.route.code,
            upstream_url=upstream_url,
            stage="upstream_retry",
            error=error,
            retry_count=max(attempt_number - 1, 0),
            extra={"attempt_number": attempt_number, "status_code": status_code},
        )

    def create_stream_observer(
        self,
        *,
        context: RequestContext,
        route_resolution: RouteResolution,
        upstream_url: str,
        status_code: int,
        request_started_at: float,
        response_started_at: float,
        retry_count: int,
        response_headers: dict[str, str],
        content_type: str | None,
    ) -> StreamDebugObserver | None:
        if not self.enabled:
            return None
        return StreamDebugObserver(
            logger=self,
            context=context,
            route_resolution=route_resolution,
            upstream_url=upstream_url,
            status_code=status_code,
            request_started_at=request_started_at,
            response_started_at=response_started_at,
            retry_count=retry_count,
            sanitized_response_headers=response_headers,
            content_type=content_type,
            max_logged_body_bytes=self.max_response_body_bytes,
            max_chunk_previews=self.max_stream_chunk_previews,
        )
