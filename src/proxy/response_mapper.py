from __future__ import annotations

import httpx

from src.routes.registry import RouteResolution
from src.security.header_allowlist import sanitize_response_headers


def map_response_headers(
    response: httpx.Response, route_resolution: RouteResolution
) -> dict[str, str]:
    allowed = route_resolution.route.forwarding.response_headers
    return sanitize_response_headers(dict(response.headers), allowed_headers=allowed)
