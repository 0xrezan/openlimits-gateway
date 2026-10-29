from __future__ import annotations

from src.bootstrap import GatewayContainer
from src.observability.logging import get_logger

logger = get_logger(__name__)


async def cleanup_retention(container: GatewayContainer) -> None:
    async with container.uow() as uow:
        deleted_audit = await uow.audit_logs.cleanup_older_than(
            container.settings.audit_retention_days
        )
        deleted_usage = await uow.usage.cleanup_older_than(container.settings.usage_retention_days)
    logger.info(
        "cleanup_completed",
        deleted_audit=deleted_audit,
        deleted_usage=deleted_usage,
    )
