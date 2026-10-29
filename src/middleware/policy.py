from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.core.constants import EXEMPT_PATH_PREFIXES


class PolicyMiddleware(BaseHTTPMiddleware):
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
        decision = container.policy_engine.evaluate(
            route_resolution=route_resolution,
            principal=request.state.principal,
            client_ip=request.client.host if request.client else None,
            method=request.method,
            default_body_limit_bytes=container.route_registry.snapshot.defaults.body_limit_bytes,
        )
        request.state.policy_decision = decision
        return await call_next(request)
