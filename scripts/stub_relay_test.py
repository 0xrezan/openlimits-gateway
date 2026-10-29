from __future__ import annotations

import argparse
import asyncio

import httpx

from src.core.constants import (
    API_KEY_HEADER,
    UPSTREAM_CONSUMER_HEADER,
    UPSTREAM_KEY_HEADER,
    UPSTREAM_REQUEST_ID_HEADER,
    UPSTREAM_SIGNING_HEADER,
    UPSTREAM_TIMESTAMP_HEADER,
)
from src.security.secrets import require_secret
from src.settings import get_settings


def _assert_absent(headers: dict[str, str], header_name: str) -> None:
    if header_name in headers:
        raise AssertionError(f"header {header_name!r} must not reach upstream")


def _assert_present(headers: dict[str, str], header_name: str) -> None:
    if header_name not in headers:
        raise AssertionError(f"header {header_name!r} was not injected upstream")


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    expected_service_token = require_secret(
        settings.upstream_service_token,
        "upstream_service_token",
    )

    headers = {
        API_KEY_HEADER: args.api_key,
        "forwarded": "for=198.51.100.10;proto=https",
        "x-forwarded-for": "198.51.100.10",
        "x-real-ip": "198.51.100.10",
        "via": "stub-client",
        "user-agent": "stub-relay-test",
        "content-type": "application/json",
    }
    payload = {"message": "hello through gateway"}

    async with httpx.AsyncClient(base_url=args.gateway_url, timeout=10.0) as client:
        response = await client.post(args.path, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    upstream_headers = data["headers"]
    _assert_absent(upstream_headers, API_KEY_HEADER)
    _assert_absent(upstream_headers, "forwarded")
    _assert_absent(upstream_headers, "x-forwarded-for")
    _assert_absent(upstream_headers, "x-real-ip")
    _assert_absent(upstream_headers, "via")

    authorization = upstream_headers.get("authorization")
    if authorization != f"Bearer {expected_service_token}":
        raise AssertionError("gateway did not inject the expected upstream authorization header")

    _assert_present(upstream_headers, UPSTREAM_CONSUMER_HEADER)
    _assert_present(upstream_headers, UPSTREAM_KEY_HEADER)
    _assert_present(upstream_headers, UPSTREAM_REQUEST_ID_HEADER)

    if settings.upstream_signing_enabled:
        _assert_present(upstream_headers, UPSTREAM_SIGNING_HEADER)
        _assert_present(upstream_headers, UPSTREAM_TIMESTAMP_HEADER)

    print("stub relay test passed")
    print(f"upstream path: {data['path']}")
    print(f"consumer header: {upstream_headers[UPSTREAM_CONSUMER_HEADER]}")
    print(f"key header: {upstream_headers[UPSTREAM_KEY_HEADER]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exercise the gateway against a local mock upstream.",
    )
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8080")
    parser.add_argument("--path", default="/api/echo")
    parser.add_argument("--api-key", required=True)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
