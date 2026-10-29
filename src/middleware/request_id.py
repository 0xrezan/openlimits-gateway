from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from src.core.constants import REQUEST_ID_HEADER
from src.core.context import RequestContext, clear_request_context, set_request_context


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid4()))
        context = RequestContext(
            request_id=request_id,
            client_host=request.client.host if request.client else None,
        )
        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            client_host=context.client_host,
        )
        request.state.request_context = context
        set_request_context(context)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
            clear_contextvars()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
