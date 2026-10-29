from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.observability.events import AuditEvent
from src.storage.models import AuditLog


class AuditService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, event: AuditEvent) -> None:
        async with self._session_factory() as session:
            session.add(
                AuditLog(
                    actor_type=event.actor_type.value,
                    actor_id=event.actor_id,
                    event_type=event.event_type.value,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    request_id=event.request_id,
                    detail=event.detail,
                    created_at=event.created_at,
                )
            )
            await session.commit()
