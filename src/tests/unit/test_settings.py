from __future__ import annotations

import pytest

from src.settings import Settings


def _base_settings_payload() -> dict[str, object]:
    return {
        "database_url": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "redis_url": "redis://localhost:6379/0",
        "upstream_base_url": "https://main.internal",
        "upstream_service_token": "svc-token",
        "upstream_signing_enabled": False,
    }


def test_admin_allowlist_normalizes_plain_ips() -> None:
    settings = Settings.model_validate(
        {
            **_base_settings_payload(),
            "admin_api_ip_allowlist": ["127.0.0.1", "10.0.0.0/24"],
        }
    )
    assert settings.admin_api_ip_allowlist == ["127.0.0.1/32", "10.0.0.0/24"]


def test_admin_allowlist_rejects_invalid_cidr() -> None:
    with pytest.raises(ValueError):
        Settings.model_validate(
            {
                **_base_settings_payload(),
                "admin_api_ip_allowlist": ["not-a-network"],
            }
        )
