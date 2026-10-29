from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars

from src.core.constants import API_KEY_HEADER, EXEMPT_PATH_PREFIXES
from src.core.exceptions import AuthenticationError


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if any(request.url.path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
            return await call_next(request)
        container = request.app.state.container
        auth_failure_limit = container.route_registry.snapshot.limits.get("auth_failures")
        client_identifier = (
            request.client.host if request.client and request.client.host else "unknown"
        )
        if auth_failure_limit is not None:
            await container.auth_failure_limiter.check(
                client_identifier=client_identifier,
                requests=auth_failure_limit["requests"],
                window_seconds=auth_failure_limit["window_seconds"],
            )
        presented_key = request.headers.get(API_KEY_HEADER)
        if presented_key is None:
            authorization = request.headers.get("authorization")
            if authorization and authorization.lower().startswith("bearer "):
                presented_key = authorization.split(" ", 1)[1].strip()
        if not presented_key:
            if auth_failure_limit is not None:
                await container.auth_failure_limiter.record_failure(
                    client_identifier=client_identifier,
                    requests=auth_failure_limit["requests"],
                    window_seconds=auth_failure_limit["window_seconds"],
                )
            raise AuthenticationError("missing api key")
        try:
            async with container.uow() as uow:
                principal = await container.key_service.authenticate(uow, presented_key)
        except AuthenticationError:
            if auth_failure_limit is not None:
                await container.auth_failure_limiter.record_failure(
                    client_identifier=client_identifier,
                    requests=auth_failure_limit["requests"],
                    window_seconds=auth_failure_limit["window_seconds"],
                )
            raise
        if auth_failure_limit is not None:
            await container.auth_failure_limiter.reset(
                client_identifier=client_identifier,
                window_seconds=auth_failure_limit["window_seconds"],
            )
        request.state.principal = principal
        request.state.request_context.consumer_id = principal.consumer_id
        request.state.request_context.consumer_name = principal.consumer_name
        request.state.request_context.key_id = principal.key_id
        request.state.request_context.key_name = principal.key_name
        request.state.request_context.key_prefix = principal.key_prefix
        bind_contextvars(
            consumer_id=str(principal.consumer_id),
            consumer_name=principal.consumer_name,
            key_id=str(principal.key_id),
            key_name=principal.key_name,
            key_prefix=principal.key_prefix,
        )
        return await call_next(request)
