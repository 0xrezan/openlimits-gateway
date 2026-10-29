from __future__ import annotations

from src.bootstrap import GatewayContainer
from src.observability.logging import get_logger

logger = get_logger(__name__)


async def warm_caches(container: GatewayContainer) -> None:
    logger.info(
        "cache_warmup",
        routes=len(container.route_registry.snapshot.routes),
        policies=len(container.route_registry.snapshot.policies),
    )
