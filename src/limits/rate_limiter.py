from __future__ import annotations

from time import time
from uuid import UUID

from src.core.exceptions import RateLimitExceededError
from src.limits.keys import auth_failure_key, rate_limit_key
from src.limits.redis_backend import CounterBackend


def _window_data(window_seconds: int) -> tuple[int, int]:
    now = int(time())
    window_bucket = now // window_seconds
    retry_after = max(window_seconds - (now % window_seconds), 1)
    return window_bucket, retry_after


class RateLimiter:
    def __init__(self, backend: CounterBackend) -> None:
        self._backend = backend

    async def enforce(
        self,
        *,
        consumer_id: UUID,
        route_code: str,
        requests: int,
        window_seconds: int,
    ) -> None:
        window_bucket, retry_after = _window_data(window_seconds)
        key = rate_limit_key(
            consumer_id=str(consumer_id),
            route_code=route_code,
            window_bucket=window_bucket,
        )
        current = await self._backend.increment(key, ttl_seconds=window_seconds)
        if current > requests:
            raise RateLimitExceededError(retry_after_seconds=max(retry_after, 1))


class AuthFailureLimiter:
    def __init__(self, backend: CounterBackend) -> None:
        self._backend = backend

    async def check(
        self,
        *,
        client_identifier: str,
        requests: int,
        window_seconds: int,
    ) -> None:
        window_bucket, retry_after = _window_data(window_seconds)
        key = auth_failure_key(
            client_identifier=client_identifier,
            window_bucket=window_bucket,
        )
        current = await self._backend.get(key)
        if current >= requests:
            raise RateLimitExceededError(
                retry_after_seconds=retry_after,
                message="too many authentication failures",
            )

    async def record_failure(
        self,
        *,
        client_identifier: str,
        requests: int,
        window_seconds: int,
    ) -> None:
        window_bucket, retry_after = _window_data(window_seconds)
        key = auth_failure_key(
            client_identifier=client_identifier,
            window_bucket=window_bucket,
        )
        current = await self._backend.increment(key, ttl_seconds=window_seconds)
        if current > requests:
            raise RateLimitExceededError(
                retry_after_seconds=retry_after,
                message="too many authentication failures",
            )

    async def reset(self, *, client_identifier: str, window_seconds: int) -> None:
        window_bucket, _ = _window_data(window_seconds)
        key = auth_failure_key(
            client_identifier=client_identifier,
            window_bucket=window_bucket,
        )
        await self._backend.delete(key)
