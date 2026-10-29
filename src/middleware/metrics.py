from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        container = request.app.state.container
        route_resolution = getattr(request.state, "route_resolution", None)
        route_label = (
            route_resolution.route.code if route_resolution is not None else request.url.path
        )
        status_family = f"{response.status_code // 100}xx"
        container.metrics.requests_total.labels(
            route=route_label,
            method=request.method,
            status_family=status_family,
        ).inc()
        return response
