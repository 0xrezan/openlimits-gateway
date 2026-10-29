from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars

from src.core.constants import EXEMPT_PATH_PREFIXES


class RouteResolverMiddleware(BaseHTTPMiddleware):
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
        request.state.route_resolution = route_resolution
        request.state.request_context.route_code = route_resolution.route.code
        request.state.request_context.route_id = route_resolution.route.code
        bind_contextvars(
            route_code=route_resolution.route.code,
            route_id=route_resolution.route.code,
        )
        return await call_next(request)
