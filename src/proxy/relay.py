from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, cast

import httpx
from fastapi import Request, Response

from src.core.context import RequestContext
from src.core.exceptions import UpstreamServiceError, UpstreamTimeoutError
from src.observability.debug_http_logging import (
    DebugHTTPLogger,
    build_body_log,
    is_streaming_response,
    sanitize_headers,
)
from src.observability.metrics import GatewayMetrics
from src.proxy.bulkhead import BulkheadRegistry
from src.proxy.circuit_breaker import CircuitBreakerRegistry
from src.proxy.header_policy import build_upstream_request_headers
from src.proxy.response_mapper import map_response_headers
from src.proxy.retry import RetryableUpstreamError, RetryPolicyContext, build_retrying
from src.proxy.streaming import build_streaming_response, request_expects_streaming
from src.proxy.timeouts import build_timeout
from src.routes.registry import RouteResolution
from src.settings import Settings


@dataclass(slots=True)
class RelayResult:
    response: Response
    status_code: int
    latency_seconds: float
    bytes_in: int
    bytes_out: int
    stream_mode: bool
    retry_count: int
    upstream_url: str


@dataclass(slots=True)
class UpstreamSendResult:
    response: httpx.Response
    attempt_count: int


class RelayService:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        settings: Settings,
        metrics: GatewayMetrics,
        debug_logger: DebugHTTPLogger,
        circuit_breakers: CircuitBreakerRegistry,
        bulkheads: BulkheadRegistry,
    ) -> None:
        self._client = client
        self._settings = settings
        self._metrics = metrics
        self._debug_logger = debug_logger
        self._circuit_breakers = circuit_breakers
        self._bulkheads = bulkheads

    async def close(self) -> None:
        await self._client.aclose()

    async def relay(
        self,
        *,
        request: Request,
        route_resolution: RouteResolution,
        context: RequestContext,
        allowed_headers: list[str],
        identity_headers: dict[str, str],
        body: bytes,
    ) -> RelayResult:
        prepare_started = monotonic()
        headers = build_upstream_request_headers(
            inbound_headers=request.headers,
            allowed_headers=allowed_headers,
            identity_headers=identity_headers,
        )
        path_with_query = route_resolution.upstream_path
        if request.url.query:
            path_with_query = f"{path_with_query}?{request.url.query}"
        upstream_url = str(self._client.base_url.join(path_with_query))
        request_streaming = self._should_stream_upstream_request(request=request, body=body)
        preparation_ms = round((monotonic() - prepare_started) * 1000, 2)
        self._debug_logger.log_upstream_request_sent(
            context=context,
            route_resolution=route_resolution,
            upstream_url=upstream_url,
            method=request.method,
            headers=headers,
            body=body,
            preparation_ms=preparation_ms,
            request_streaming=request_streaming,
        )

        breaker = self._circuit_breakers.get(
            route_code=route_resolution.route.code,
            failure_threshold=route_resolution.route.circuit_breaker.failure_threshold,
            recovery_timeout_seconds=route_resolution.route.circuit_breaker.recovery_timeout_seconds,
            half_open_max_requests=route_resolution.route.circuit_breaker.half_open_max_requests,
        )
        self._metrics.circuit_state.labels(route=route_resolution.route.code).set(
            breaker.state_value
        )
        breaker.allow_request()
        semaphore = self._bulkheads.get(
            route_resolution.route.code,
            route_resolution.route.bulkhead.max_concurrency,
        )
        request_started = monotonic()

        async with semaphore:
            try:
                send_result = await self._send_with_retry(
                    method=request.method,
                    path_with_query=path_with_query,
                    headers=headers,
                    body=body,
                    route_resolution=route_resolution,
                    context=context,
                    upstream_url=upstream_url,
                    use_stream_transport=request_streaming,
                )
            except httpx.TimeoutException as error:
                breaker.on_failure()
                retry_count = max(int(getattr(error, "attempt_number", 1)) - 1, 0)
                self._metrics.upstream_timeouts_total.labels(
                    route=route_resolution.route.code
                ).inc()
                self._debug_logger.log_relay_error(
                    context=context,
                    route_code=route_resolution.route.code,
                    upstream_url=upstream_url,
                    stage="upstream_request",
                    error=error,
                    retry_count=retry_count,
                )
                raise UpstreamTimeoutError() from error
            except RetryableUpstreamError as error:
                breaker.on_failure()
                retry_count = max(error.attempt_number - 1, 0)
                self._debug_logger.log_relay_error(
                    context=context,
                    route_code=route_resolution.route.code,
                    upstream_url=upstream_url,
                    stage="upstream_request",
                    error=error,
                    retry_count=retry_count,
                    extra={"status_code": error.response.status_code},
                )
                raise UpstreamServiceError(
                    f"upstream returned {error.response.status_code} after retries",
                    status_code=error.response.status_code,
                ) from error
            except httpx.TransportError as error:
                breaker.on_failure()
                retry_count = max(int(getattr(error, "attempt_number", 1)) - 1, 0)
                self._debug_logger.log_relay_error(
                    context=context,
                    route_code=route_resolution.route.code,
                    upstream_url=upstream_url,
                    stage="upstream_request",
                    error=error,
                    retry_count=retry_count,
                )
                raise UpstreamServiceError() from error

        response = send_result.response
        retry_count = max(send_result.attempt_count - 1, 0)
        response_received_at = monotonic()
        stream_mode = is_streaming_response(response.headers)
        response_headers = map_response_headers(response, route_resolution)
        sanitized_response_headers = sanitize_headers(response_headers)

        if stream_mode:
            if response.status_code >= 500:
                breaker.on_failure()
            else:
                breaker.on_success()
            self._metrics.circuit_state.labels(route=route_resolution.route.code).set(
                breaker.state_value
            )
            latency = response_received_at - request_started
            self._metrics.upstream_latency_seconds.labels(
                route=route_resolution.route.code,
                method=request.method,
            ).observe(latency)
            self._debug_logger.log_upstream_response_received(
                context=context,
                route_resolution=route_resolution,
                upstream_url=upstream_url,
                response=response,
                upstream_duration_ms=round(latency * 1000, 2),
                stream_mode=True,
                retry_count=retry_count,
            )
            observer = self._debug_logger.create_stream_observer(
                context=context,
                route_resolution=route_resolution,
                upstream_url=upstream_url,
                status_code=response.status_code,
                request_started_at=request_started,
                response_started_at=response_received_at,
                retry_count=retry_count,
                response_headers=sanitized_response_headers,
                content_type=sanitized_response_headers.get("content-type"),
            )
            downstream = build_streaming_response(
                status_code=response.status_code,
                headers=response_headers,
                upstream_response=response,
                observer=observer,
            )
            return RelayResult(
                response=downstream,
                status_code=response.status_code,
                latency_seconds=latency,
                bytes_in=len(body),
                bytes_out=int(response.headers.get("content-length", "0")),
                stream_mode=True,
                retry_count=retry_count,
                upstream_url=upstream_url,
            )

        response_body = await response.aread()
        if response.status_code >= 500:
            breaker.on_failure()
        else:
            breaker.on_success()
        self._metrics.circuit_state.labels(route=route_resolution.route.code).set(
            breaker.state_value
        )
        latency = monotonic() - request_started
        self._metrics.upstream_latency_seconds.labels(
            route=route_resolution.route.code,
            method=request.method,
        ).observe(latency)
        self._debug_logger.log_upstream_response_received(
            context=context,
            route_resolution=route_resolution,
            upstream_url=upstream_url,
            response=response,
            upstream_duration_ms=round(latency * 1000, 2),
            stream_mode=False,
            retry_count=retry_count,
            body=response_body,
        )
        downstream = Response(
            content=response_body,
            status_code=response.status_code,
            headers=response_headers,
        )
        self._debug_logger.log_relay_response_sent(
            context=context,
            route_code=route_resolution.route.code,
            upstream_url=upstream_url,
            status_code=response.status_code,
            stream_mode=False,
            total_duration_ms=round(latency * 1000, 2),
            retry_count=retry_count,
            response_headers=sanitized_response_headers,
            **build_body_log(
                response_body,
                content_type=sanitized_response_headers.get("content-type"),
                max_bytes=self._debug_logger.max_response_body_bytes,
            ),
        )
        return RelayResult(
            response=downstream,
            status_code=response.status_code,
            latency_seconds=latency,
            bytes_in=len(body),
            bytes_out=len(response_body),
            stream_mode=False,
            retry_count=retry_count,
            upstream_url=upstream_url,
        )

    def _should_stream_upstream_request(self, *, request: Request, body: bytes) -> bool:
        mode = self._settings.upstream_stream_transport_mode
        if mode == "always":
            return True
        if mode == "never":
            return False
        return request_expects_streaming(request, body)

    async def _send_with_retry(
        self,
        *,
        method: str,
        path_with_query: str,
        headers: dict[str, str],
        body: bytes,
        route_resolution: RouteResolution,
        context: RequestContext,
        upstream_url: str,
        use_stream_transport: bool,
    ) -> UpstreamSendResult:
        retry_context = RetryPolicyContext(
            enabled=route_resolution.route.retry.enabled,
            attempts=route_resolution.route.retry.attempts,
            retry_on_statuses=route_resolution.route.retry.retry_on_statuses,
            base_delay_ms=route_resolution.route.retry.base_delay_ms,
            max_delay_ms=route_resolution.route.retry.max_delay_ms,
        )
        timeout = build_timeout(self._settings, route_resolution)
        timeout_extensions = {"timeout": timeout.as_dict()}

        if not retry_context.enabled:
            response = await self._send_once(
                method=method,
                path_with_query=path_with_query,
                headers=headers,
                body=body,
                request_timeout=timeout,
                timeout_extensions=timeout_extensions,
                use_stream_transport=use_stream_transport,
            )
            return UpstreamSendResult(response=response, attempt_count=1)

        attempt_number = 0
        async for attempt in build_retrying(retry_context):
            attempt_number = attempt.retry_state.attempt_number
            with attempt:
                try:
                    response = await self._send_once(
                        method=method,
                        path_with_query=path_with_query,
                        headers=headers,
                        body=body,
                        request_timeout=timeout,
                        timeout_extensions=timeout_extensions,
                        use_stream_transport=use_stream_transport,
                    )
                except (httpx.TimeoutException, httpx.TransportError) as error:
                    cast(Any, error).attempt_number = attempt_number
                    if attempt_number < retry_context.attempts:
                        self._debug_logger.log_upstream_retry(
                            context=context,
                            route_resolution=route_resolution,
                            upstream_url=upstream_url,
                            attempt_number=attempt_number,
                            error=error,
                        )
                    raise
                retryable_methods = route_resolution.route.retry.retryable_methods
                should_retry = (
                    response.status_code in retry_context.retry_on_statuses
                    and method.upper() in retryable_methods
                )
                if should_retry:
                    self._metrics.retries_total.labels(
                        route=route_resolution.route.code,
                        reason=str(response.status_code),
                    ).inc()
                    retry_error = RetryableUpstreamError(response, attempt_number)
                    if attempt_number < retry_context.attempts:
                        self._debug_logger.log_upstream_retry(
                            context=context,
                            route_resolution=route_resolution,
                            upstream_url=upstream_url,
                            attempt_number=attempt_number,
                            error=retry_error,
                            status_code=response.status_code,
                        )
                    await response.aclose()
                    raise retry_error
                return UpstreamSendResult(response=response, attempt_count=attempt_number)
        raise UpstreamServiceError("unreachable retry state")

    async def _send_once(
        self,
        *,
        method: str,
        path_with_query: str,
        headers: dict[str, str],
        body: bytes,
        request_timeout: httpx.Timeout,
        timeout_extensions: dict[str, dict[str, float | None]],
        use_stream_transport: bool,
    ) -> httpx.Response:
        if not use_stream_transport:
            return await self._client.request(
                method,
                path_with_query,
                headers=headers,
                content=body,
                timeout=request_timeout,
            )

        request = self._client.build_request(
            method,
            path_with_query,
            headers=headers,
            content=body,
            extensions=timeout_extensions,
        )
        return await self._client.send(request, stream=True)
