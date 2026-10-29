from __future__ import annotations

import httpx

from src.routes.registry import RouteResolution
from src.settings import Settings


def build_timeout(settings: Settings, route_resolution: RouteResolution) -> httpx.Timeout:
    return httpx.Timeout(
        timeout=route_resolution.route.timeout_ms / 1000,
        connect=settings.connect_timeout_ms / 1000,
        pool=settings.pool_timeout_ms / 1000,
    )
