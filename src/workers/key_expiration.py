from __future__ import annotations

from src.bootstrap import GatewayContainer
from src.observability.logging import get_logger

logger = get_logger(__name__)


async def revoke_expired_keys(container: GatewayContainer) -> None:
    async with container.uow() as uow:
        revoked = await uow.api_keys.revoke_expired()
    logger.info("expired_keys_revoked", count=revoked)
