from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import Consumer


class ConsumerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        description: str | None,
        allowed_ips: list[str],
        metadata_json: dict[str, object],
    ) -> Consumer:
        consumer = Consumer(
            name=name,
            description=description,
            allowed_ips=allowed_ips,
            metadata_json=dict(metadata_json),
        )
        self._session.add(consumer)
        await self._session.flush()
        return consumer

    async def get(self, consumer_id: UUID) -> Consumer | None:
        return await self._session.get(Consumer, consumer_id)

    async def get_by_name(self, name: str) -> Consumer | None:
        result = await self._session.execute(select(Consumer).where(Consumer.name == name))
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[Consumer]:
        result = await self._session.execute(select(Consumer).order_by(Consumer.created_at.desc()))
        return result.scalars().all()
