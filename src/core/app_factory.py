from __future__ import annotations

from fastapi import FastAPI

from src.api.admin import router as admin_router
from src.api.health import router as health_router
from src.api.metrics import router as metrics_router
from src.api.public import router as public_router
from src.core.lifecycle import build_lifespan
from src.middleware.access_log import AccessLogMiddleware
from src.middleware.auth import AuthMiddleware
from src.middleware.body_limits import BodyLimitsMiddleware
from src.middleware.concurrency_guard import ConcurrencyGuardMiddleware
from src.middleware.error_mapper import register_exception_handlers
from src.middleware.header_sanitizer import HeaderSanitizerMiddleware
from src.middleware.metrics import MetricsMiddleware
from src.middleware.policy import PolicyMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.request_id import RequestIDMiddleware
from src.middleware.route_resolver import RouteResolverMiddleware
from src.middleware.upstream_identity import UpstreamIdentityMiddleware
from src.observability.tracing import configure_tracing
from src.settings import Settings


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="OpenLimits VPS Gateway",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=build_lifespan(settings),
    )

    register_exception_handlers(app)

    # Starlette executes the most recently added middleware first on the request path.
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(UpstreamIdentityMiddleware)
    app.add_middleware(HeaderSanitizerMiddleware)
    app.add_middleware(RouteResolverMiddleware)
    app.add_middleware(PolicyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(BodyLimitsMiddleware)
    app.add_middleware(ConcurrencyGuardMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(admin_router)
    app.include_router(public_router)

    configure_tracing(app, settings)
    return app
