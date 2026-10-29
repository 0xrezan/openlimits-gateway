from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress

from fastapi import FastAPI

from src.bootstrap import create_container
from src.observability.logging import get_logger
from src.settings import Settings

logger = get_logger(__name__)


async def _config_reload_loop(app: FastAPI, interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            changed = app.state.container.config_watcher.reload_if_changed()
            if changed:
                await app.state.container.sync_runtime_config_to_db()
        except Exception:
            logger.exception("config_reload_failed")


def build_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = await create_container(settings)
        app.state.container = container
        reload_task = asyncio.create_task(
            _config_reload_loop(app, settings.config_reload_interval_seconds)
        )
        app.state.reload_task = reload_task
        try:
            yield
        finally:
            reload_task.cancel()
            with suppress(asyncio.CancelledError):
                await reload_task
            await container.close()

    return lifespan
