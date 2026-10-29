from __future__ import annotations

import ssl

import httpx

from src.security.mTLS import build_ssl_context
from src.settings import Settings


def build_http_client(settings: Settings) -> httpx.AsyncClient:
    limits = httpx.Limits(
        max_connections=settings.max_connections,
        max_keepalive_connections=settings.max_keepalive_connections,
    )
    timeout = httpx.Timeout(
        timeout=settings.request_timeout_ms / 1000,
        connect=settings.connect_timeout_ms / 1000,
        pool=settings.pool_timeout_ms / 1000,
    )
    verify: ssl.SSLContext | bool = build_ssl_context(settings) or True
    return httpx.AsyncClient(
        base_url=settings.upstream_base_url,
        follow_redirects=False,
        timeout=timeout,
        limits=limits,
        verify=verify,
    )
