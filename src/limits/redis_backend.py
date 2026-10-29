from __future__ import annotations

from typing import Any, Protocol


class CounterBackend(Protocol):
    async def increment(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int: ...

    async def get(self, key: str) -> int: ...

    async def delete(self, key: str) -> None: ...


class RedisCounterBackend:
    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def increment(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        current = await self._redis.incrby(key, amount)
        if current == amount:
            await self._redis.expire(key, ttl_seconds)
        return int(current)

    async def get(self, key: str) -> int:
        value = await self._redis.get(key)
        return int(value) if value is not None else 0

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)
