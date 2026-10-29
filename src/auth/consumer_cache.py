from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis


@dataclass(slots=True)
class CachedPrincipal:
    consumer_id: str
    consumer_name: str
    consumer_status: str
    consumer_allowed_ips: list[str]
    key_id: str
    key_name: str
    key_hash: str
    key_prefix: str
    key_expires_at: str | None
    key_revoked_at: str | None
    scopes: list[str]

    def expires_at(self) -> datetime | None:
        return datetime.fromisoformat(self.key_expires_at) if self.key_expires_at else None

    def revoked_at(self) -> datetime | None:
        return datetime.fromisoformat(self.key_revoked_at) if self.key_revoked_at else None


class ConsumerCache:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _key(prefix: str) -> str:
        return f"consumer_cache:{prefix}"

    async def get(self, prefix: str) -> CachedPrincipal | None:
        payload = await self._redis.get(self._key(prefix))
        if payload is None:
            return None
        data = json.loads(payload)
        return CachedPrincipal(**data)

    async def set(self, principal: CachedPrincipal) -> None:
        await self._redis.set(
            self._key(principal.key_prefix),
            json.dumps(asdict(principal)),
            ex=self._ttl_seconds,
        )

    async def invalidate(self, prefix: str) -> None:
        await self._redis.delete(self._key(prefix))

    @classmethod
    def from_orm(
        cls,
        *,
        consumer_id: UUID,
        consumer_name: str,
        consumer_status: str,
        consumer_allowed_ips: list[str],
        key_id: UUID,
        key_name: str,
        key_hash: str,
        key_prefix: str,
        key_expires_at: datetime | None,
        key_revoked_at: datetime | None,
        scopes: list[str],
    ) -> CachedPrincipal:
        return CachedPrincipal(
            consumer_id=str(consumer_id),
            consumer_name=consumer_name,
            consumer_status=consumer_status,
            consumer_allowed_ips=consumer_allowed_ips,
            key_id=str(key_id),
            key_name=key_name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            key_expires_at=key_expires_at.astimezone(UTC).isoformat() if key_expires_at else None,
            key_revoked_at=key_revoked_at.astimezone(UTC).isoformat() if key_revoked_at else None,
            scopes=scopes,
        )
