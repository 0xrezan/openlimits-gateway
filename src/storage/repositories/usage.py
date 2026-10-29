from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import Usage


def bucket_start_for(granularity: str, now: datetime) -> datetime:
    if granularity == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "hour":
        return now.replace(minute=0, second=0, microsecond=0)
    return now.replace(second=0, microsecond=0)


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        consumer_id: UUID,
        key_id: UUID,
        route_code: str,
        success: bool,
        bytes_in: int,
        bytes_out: int,
        granularity: str = "minute",
    ) -> Usage:
        now = datetime.now(UTC)
        bucket_start = bucket_start_for(granularity, now)
        result = await self._session.execute(
            select(Usage).where(
                Usage.consumer_id == consumer_id,
                Usage.key_id == key_id,
                Usage.route_code == route_code,
                Usage.bucket_start == bucket_start,
                Usage.bucket_granularity == granularity,
            )
        )
        usage = result.scalar_one_or_none()
        if usage is None:
            usage = Usage(
                consumer_id=consumer_id,
                key_id=key_id,
                route_code=route_code,
                bucket_start=bucket_start,
                bucket_granularity=granularity,
                request_count=0,
                success_count=0,
                error_count=0,
                bytes_in=0,
                bytes_out=0,
            )
            self._session.add(usage)
        usage.request_count += 1
        usage.success_count += 1 if success else 0
        usage.error_count += 0 if success else 1
        usage.bytes_in += bytes_in
        usage.bytes_out += bytes_out
        usage.last_seen_at = now
        await self._session.flush()
        return usage

    async def list_recent_for_consumer(self, consumer_id: UUID, limit: int = 100) -> list[Usage]:
        result = await self._session.execute(
            select(Usage)
            .where(Usage.consumer_id == consumer_id)
            .order_by(Usage.last_seen_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def cleanup_older_than(self, days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            delete(Usage).where(Usage.last_seen_at < cutoff).returning(Usage.id)
        )
        return len(result.scalars().all())
