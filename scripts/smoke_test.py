from __future__ import annotations

import asyncio

import httpx

from src.settings import get_settings


async def _run() -> None:
    settings = get_settings()
    base_url = f"http://{settings.host}:{settings.port}"
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        response = await client.get("/healthz")
        response.raise_for_status()
        print(f"healthz={response.json()}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
