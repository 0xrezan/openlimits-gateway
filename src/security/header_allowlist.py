from __future__ import annotations

from collections.abc import Mapping

from src.core.constants import (
    DEFAULT_REQUEST_HEADER_ALLOWLIST,
    DEFAULT_RESPONSE_HEADER_ALLOWLIST,
    FORWARDED_HEADERS_TO_STRIP,
    SENSITIVE_HEADERS,
)


def sanitize_inbound_headers(
    headers: Mapping[str, str],
    *,
    allowed_headers: list[str] | set[str] | None = None,
) -> dict[str, str]:
    allowlist = {header.lower() for header in (allowed_headers or DEFAULT_REQUEST_HEADER_ALLOWLIST)}
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in FORWARDED_HEADERS_TO_STRIP or lowered in SENSITIVE_HEADERS:
            continue
        if lowered in allowlist:
            sanitized[key] = value
    return sanitized


def sanitize_response_headers(
    headers: Mapping[str, str],
    *,
    allowed_headers: list[str] | set[str] | None = None,
) -> dict[str, str]:
    allowlist = {
        header.lower() for header in (allowed_headers or DEFAULT_RESPONSE_HEADER_ALLOWLIST)
    }
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in allowlist:
            sanitized[key] = value
    return sanitized
