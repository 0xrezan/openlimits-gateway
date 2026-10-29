from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.core.constants import EXEMPT_PATH_PREFIXES


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if any(request.url.path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
            return await call_next(request)
        container = request.app.state.container
        route_resolution = getattr(request.state, "route_resolution_candidate", None)
        if route_resolution is None:
            route_resolution = container.route_registry.resolve(request.url.path, request.method)
            request.state.route_resolution_candidate = route_resolution
        principal = request.state.principal
        policy = route_resolution.policy
        await container.rate_limiter.enforce(
            consumer_id=principal.consumer_id,
            route_code=route_resolution.route.code,
            requests=policy.rate_limit.requests,
            window_seconds=policy.rate_limit.window_seconds,
        )
        for quota in policy.quotas:
            await container.quota_store.enforce(
                consumer_id=principal.consumer_id,
                route_code=route_resolution.route.code,
                quota_name=quota.name,
                requests=quota.requests,
                window_seconds=quota.window_seconds,
            )
        return await call_next(request)
