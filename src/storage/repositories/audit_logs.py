from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(self, limit: int = 100) -> list[AuditLog]:
        result = await self._session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get(self, audit_id: UUID) -> AuditLog | None:
        return await self._session.get(AuditLog, audit_id)

    async def cleanup_older_than(self, days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff).returning(AuditLog.id)
        )
        return len(result.scalars().all())
