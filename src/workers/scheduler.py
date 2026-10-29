from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from src.bootstrap import create_container
from src.observability.logging import get_logger
from src.settings import get_settings
from src.workers.cache_warmup import warm_caches
from src.workers.cleanup import cleanup_retention
from src.workers.key_expiration import revoke_expired_keys
from src.workers.quota_reset import run_quota_reset

logger = get_logger(__name__)


async def run_scheduler() -> None:
    settings = get_settings()
    container = await create_container(settings)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_quota_reset, "interval", minutes=15, id="quota_reset")
    scheduler.add_job(warm_caches, "interval", minutes=10, id="cache_warmup", args=[container])
    scheduler.add_job(
        revoke_expired_keys, "interval", minutes=5, id="key_expiration", args=[container]
    )
    scheduler.add_job(cleanup_retention, "interval", hours=1, id="cleanup", args=[container])
    scheduler.start()
    logger.info("worker_scheduler_started")
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await container.close()


def main() -> None:
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
