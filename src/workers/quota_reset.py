from __future__ import annotations

from src.observability.logging import get_logger

logger = get_logger(__name__)


async def run_quota_reset() -> None:
    # Redis TTL-backed quota windows self-reset automatically; this job is a visibility hook.
    logger.info("quota_reset_tick", strategy="ttl_windows")
