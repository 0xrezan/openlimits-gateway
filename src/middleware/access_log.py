from __future__ import annotations

from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.observability.logging import get_logger

logger = get_logger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        started = monotonic()
        response = await call_next(request)
        elapsed_ms = round((monotonic() - started) * 1000, 2)
        request_context = getattr(request.state, "request_context", None)
        principal = getattr(request.state, "principal", None)
        logger.info(
            "access_log",
            request_id=request_context.request_id if request_context else None,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=elapsed_ms,
            consumer_id=str(principal.consumer_id) if principal else None,
        )
        return response
