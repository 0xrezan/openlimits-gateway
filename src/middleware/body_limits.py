from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.core.exceptions import BodyTooLargeError


class BodyLimitsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        max_bytes = request.app.state.container.settings.max_request_body_bytes
        content_length = request.headers.get("content-length")
        if content_length is not None:
            declared_size = int(content_length)
            if declared_size > max_bytes:
                raise BodyTooLargeError()
        body = await request.body()
        if len(body) > max_bytes:
            raise BodyTooLargeError()
        return await call_next(request)
