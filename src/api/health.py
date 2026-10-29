from __future__ import annotations

import httpx
from fastapi import APIRouter, Request

from src.storage.db import database_healthcheck

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, object]:
    container = request.app.state.container
    await database_healthcheck(container.engine)
    await container.redis.ping()
    upstream_status: str = "skipped"
    if container.settings.enable_real_upstream_healthcheck:
        async with httpx.AsyncClient(
            base_url=container.settings.upstream_base_url, timeout=5.0
        ) as client:
            response = await client.get("/")
            upstream_status = str(response.status_code)
    return {"status": "ready", "upstream": upstream_status}
