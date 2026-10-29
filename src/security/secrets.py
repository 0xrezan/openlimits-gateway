from __future__ import annotations

from pydantic import SecretStr


def require_secret(secret: SecretStr | None, name: str) -> str:
    if secret is None:
        raise ValueError(f"{name} is required")
    value = secret.get_secret_value()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def mask_secret(value: str) -> str:
    if len(value) <= 4:
        return "***REDACTED***"
    return f"{value[:2]}***REDACTED***{value[-2:]}"
