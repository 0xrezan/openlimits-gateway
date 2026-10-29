from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.enums import AuditActorType, AuditEventType
from src.core.exceptions import GatewayError
from src.observability.events import AuditEvent
from src.observability.logging import get_logger

logger = get_logger(__name__)


async def _emit_error_side_effects(request: Request, exc: GatewayError) -> None:
    container = getattr(request.app.state, "container", None)
    if container is None:
        return

    request_context = getattr(request.state, "request_context", None)
    route_resolution = getattr(request.state, "route_resolution", None)
    route_code = route_resolution.route.code if route_resolution is not None else request.url.path

    if exc.code == "authentication_failed":
        container.metrics.auth_failures_total.labels(reason=exc.message).inc()
        event_type = AuditEventType.AUTH_FAILURE
    elif exc.code == "authorization_failed":
        container.metrics.policy_denials_total.labels(reason=exc.message).inc()
        event_type = AuditEventType.POLICY_DENY
    elif exc.code == "rate_limit_exceeded":
        container.metrics.rate_limit_hits_total.labels(route=route_code).inc()
        event_type = AuditEventType.RATE_LIMIT_HIT
    elif exc.code == "upstream_timeout":
        event_type = AuditEventType.UPSTREAM_TIMEOUT
    else:
        return

    try:
        await container.audit_service.record(
            AuditEvent(
                actor_type=AuditActorType.SYSTEM,
                event_type=event_type,
                resource_type="request",
                resource_id=route_code,
                request_id=request_context.request_id if request_context else None,
                actor_id=str(getattr(getattr(request.state, "principal", None), "consumer_id", ""))
                or None,
                detail={
                    "path": request.url.path,
                    "method": request.method,
                    "error_code": exc.code,
                    "message": exc.message,
                },
            )
        )
    except Exception:
        logger.exception("audit_side_effect_failed")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GatewayError)
    async def handle_gateway_error(request: Request, exc: GatewayError) -> JSONResponse:
        request_context = getattr(request.state, "request_context", None)
        await _emit_error_side_effects(request, exc)
        logger.warning(
            "gateway_error",
            code=exc.code,
            message=exc.message,
            request_id=request_context.request_id if request_context else None,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "request_id": request_context.request_id if request_context else None,
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_context = getattr(request.state, "request_context", None)
        logger.exception(
            "unexpected_error",
            request_id=request_context.request_id if request_context else None,
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "internal server error",
                "request_id": request_context.request_id if request_context else None,
            },
        )
