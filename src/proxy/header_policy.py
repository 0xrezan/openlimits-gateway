from __future__ import annotations

from collections.abc import Mapping

from src.security.header_allowlist import sanitize_inbound_headers


def build_upstream_request_headers(
    *,
    inbound_headers: Mapping[str, str],
    allowed_headers: list[str],
    identity_headers: dict[str, str],
) -> dict[str, str]:
    headers = sanitize_inbound_headers(inbound_headers, allowed_headers=allowed_headers)
    headers.update(identity_headers)
    return headers
