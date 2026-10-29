from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class HeaderSanitizerMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        decision = getattr(request.state, "policy_decision", None)
        request.state.allowed_headers = decision.header_allowlist if decision is not None else []
        return await call_next(request)
