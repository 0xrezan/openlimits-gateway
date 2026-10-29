from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import Policy


class PolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, *, code: str, enabled: bool, config: dict[str, object], config_source: str
    ) -> Policy:
        result = await self._session.execute(select(Policy).where(Policy.code == code))
        policy = result.scalar_one_or_none()
        if policy is None:
            policy = Policy(code=code, enabled=enabled, config=config, config_source=config_source)
            self._session.add(policy)
        else:
            policy.enabled = enabled
            policy.config = config
            policy.config_source = config_source
        await self._session.flush()
        return policy

    async def list_all(self) -> Sequence[Policy]:
        result = await self._session.execute(select(Policy).order_by(Policy.code.asc()))
        return result.scalars().all()
