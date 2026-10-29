from __future__ import annotations

import re
from typing import Any

REDACTED = "***redacted***"
DEFAULT_REDACTED_KEYS = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "cookie",
    "set-cookie",
    "session-id",
    "session_id",
    "access-token",
    "access_token",
    "refresh-token",
    "refresh_token",
    "api-key",
    "api_key",
    "token",
    "secret",
    "password",
    "proxy-credentials",
    "session",
    "gateway_upstream_service_token",
    "gateway_upstream_signing_key",
}
SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "passwd",
    "session",
    "cookie",
    "credential",
)
_BEARER_RE = re.compile(r"\bBearer\s+\S+", flags=re.IGNORECASE)
_BASIC_RE = re.compile(r"\bBasic\s+\S+", flags=re.IGNORECASE)
_SECRET_TOKEN_RE = re.compile(r"\b(?:sk|rk)-[A-Za-z0-9._\-]+\b")
_GATEWAY_KEY_RE = re.compile(r"\bgk_[A-Za-z0-9._\-]+\b")


def normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_")


def is_sensitive_key(key: str) -> bool:
    normalized = normalize_key(key)
    if normalized in {normalize_key(item) for item in DEFAULT_REDACTED_KEYS}:
        return True
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_text_preview(value: str) -> str:
    redacted = _BEARER_RE.sub("Bearer ***redacted***", value)
    redacted = _BASIC_RE.sub("Basic ***redacted***", redacted)
    redacted = _SECRET_TOKEN_RE.sub("sk-***redacted***", redacted)
    redacted = _GATEWAY_KEY_RE.sub("gk_***redacted***", redacted)
    return redacted


def mask_secret_text(value: str) -> str:
    if not value:
        return REDACTED
    if value.lower().startswith("bearer "):
        return "Bearer ***redacted***"
    if value.lower().startswith("basic "):
        return "Basic ***redacted***"
    if value.startswith("sk-"):
        return "sk-***redacted***"
    if value.startswith("rk-"):
        return "rk-***redacted***"
    if value.startswith("gk_"):
        return "gk_***redacted***"
    return REDACTED


def redact_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return mask_secret_text(value)
    if isinstance(value, (bytes, bytearray)):
        return REDACTED
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def redact_mapping(data: dict[str, Any], *, keys: set[str] | None = None) -> dict[str, Any]:
    redacted_keys = {normalize_key(key) for key in (keys or DEFAULT_REDACTED_KEYS)}
    result: dict[str, Any] = {}
    for key, value in data.items():
        if normalize_key(key) in redacted_keys or is_sensitive_key(key):
            result[key] = redact_value(value)
        elif isinstance(value, dict):
            result[key] = redact_mapping(value, keys=redacted_keys)
        elif isinstance(value, list):
            result[key] = [
                redact_mapping(item, keys=redacted_keys) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = redact_text_preview(value)
        else:
            result[key] = value
    return result
