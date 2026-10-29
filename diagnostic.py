from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.settings import Settings

REQUIRED_IMPORTS = [
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "tenacity",
    "pydantic",
    "pydantic_settings",
    "yaml",
    "sqlalchemy",
    "alembic",
    "redis",
    "argon2",
    "structlog",
    "prometheus_client",
    "opentelemetry.trace",
    "opentelemetry.sdk",
    "apscheduler",
    "asyncpg",
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _fail(reason: str) -> None:
    print("\u274c ERROR:", reason)
    raise SystemExit(1)


def _assert_imports() -> None:
    missing: list[str] = []
    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)
    if missing:
        _fail(f"missing python dependencies: {', '.join(missing)}")


def _assert_paths(settings: Settings) -> None:
    required_paths = [
        settings.route_config,
        settings.policy_config,
        settings.limit_config,
        settings.logging_config,
    ]
    missing = [str(path) for path in required_paths if not Path(path).exists()]
    if missing:
        _fail(f"missing config files: {', '.join(missing)}")


def _assert_secrets(settings: Settings) -> None:
    from src.security.secrets import mask_secret, require_secret

    try:
        require_secret(settings.upstream_service_token, "upstream_service_token")
        if settings.upstream_signing_enabled:
            require_secret(settings.upstream_signing_key, "upstream_signing_key")
    except Exception as error:
        _fail(str(error))
    print(
        "Validated secrets:",
        (
            "upstream_service_token="
            f"{mask_secret(settings.upstream_service_token.get_secret_value())}"
        ),
    )


async def _connectivity_checks(settings: Settings) -> None:
    import httpx
    from redis.asyncio import Redis

    from src.storage.db import create_engine, database_healthcheck

    engine = create_engine(settings)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await database_healthcheck(engine)
        ping_result = redis.ping()
        if inspect.isawaitable(ping_result):
            await ping_result
        async with httpx.AsyncClient(
            base_url=settings.upstream_base_url,
            timeout=5.0,
        ) as client:
            response = await client.get("/")
            if response.status_code >= 500:
                _fail(f"upstream main returned {response.status_code}")
        health_host = "127.0.0.1" if settings.host == "0.0.0.0" else settings.host
        gateway_health_url = f"http://{health_host}:{settings.port}/healthz"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(gateway_health_url)
                if response.status_code >= 400:
                    _fail(f"gateway health endpoint returned {response.status_code}")
        except Exception:
            print(
                "Gateway health endpoint check skipped: gateway does not appear to be running yet."
            )
    finally:
        await redis.aclose()
        await engine.dispose()


def _validate_configs(settings: Settings) -> None:
    from src.routes.loader import load_limit_file, load_policy_file, load_route_file

    load_route_file(settings.route_config)
    load_policy_file(settings.policy_config)
    load_limit_file(settings.limit_config)


async def _main() -> None:
    _assert_imports()
    try:
        from src.settings import get_settings

        settings = get_settings()
    except Exception as error:
        _fail(f"invalid environment/settings: {error}")
        return
    _assert_paths(settings)
    _assert_secrets(settings)
    _validate_configs(settings)
    await _connectivity_checks(settings)
    print("\u2705 SYSTEM READY")


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except SystemExit:
        raise
    except Exception as error:
        _fail(str(error))
