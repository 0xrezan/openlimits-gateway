from __future__ import annotations

from src.security.header_allowlist import sanitize_inbound_headers


def test_header_sanitizer_removes_sensitive_headers() -> None:
    headers = {
        "Authorization": "Bearer secret",
        "X-Forwarded-For": "1.2.3.4",
        "Content-Type": "application/json",
    }
    sanitized = sanitize_inbound_headers(headers, allowed_headers=["content-type"])
    assert sanitized == {"Content-Type": "application/json"}
