from __future__ import annotations

from time import time
from uuid import UUID

from src.core.exceptions import QuotaExceededError
from src.limits.keys import quota_key
from src.limits.redis_backend import RedisCounterBackend


class QuotaStore:
    def __init__(self, backend: RedisCounterBackend) -> None:
        self._backend = backend

    async def enforce(
        self,
        *,
        consumer_id: UUID,
        route_code: str,
        quota_name: str,
        requests: int,
        window_seconds: int,
    ) -> None:
        now = int(time())
        window_bucket = now // window_seconds
        key = quota_key(
            consumer_id=str(consumer_id),
            route_code=route_code,
            quota_name=quota_name,
            window_bucket=window_bucket,
        )
        current = await self._backend.increment(key, ttl_seconds=window_seconds)
        if current > requests:
            raise QuotaExceededError(f"quota {quota_name!r} exceeded")
