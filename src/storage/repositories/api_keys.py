from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.storage.models import APIKey


class APIKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        consumer_id: UUID,
        name: str,
        prefix: str,
        last_four: str,
        key_hash: str,
        scopes: list[str],
        expires_at: datetime | None,
    ) -> APIKey:
        api_key = APIKey(
            consumer_id=consumer_id,
            name=name,
            prefix=prefix,
            last_four=last_four,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
        )
        self._session.add(api_key)
        await self._session.flush()
        return api_key

    async def get_with_consumer_by_prefix(self, prefix: str) -> APIKey | None:
        result = await self._session.execute(
            select(APIKey).options(selectinload(APIKey.consumer)).where(APIKey.prefix == prefix)
        )
        return result.scalar_one_or_none()

    async def get(self, key_id: UUID) -> APIKey | None:
        return await self._session.get(APIKey, key_id)

    async def revoke(self, key_id: UUID) -> APIKey | None:
        api_key = await self.get(key_id)
        if api_key is None:
            return None
        api_key.revoked_at = datetime.now(UTC)
        await self._session.flush()
        return api_key

    async def touch_last_used(self, api_key: APIKey) -> None:
        api_key.last_used_at = datetime.now(UTC)
        await self._session.flush()

    async def list_for_consumer(self, consumer_id: UUID) -> list[APIKey]:
        result = await self._session.execute(
            select(APIKey)
            .where(APIKey.consumer_id == consumer_id)
            .order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_expired(self) -> int:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(APIKey).where(
                APIKey.expires_at.is_not(None), APIKey.expires_at < now, APIKey.revoked_at.is_(None)
            )
        )
        count = 0
        for api_key in result.scalars():
            api_key.revoked_at = now
            count += 1
        await self._session.flush()
        return count
