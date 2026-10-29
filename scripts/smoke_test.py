from __future__ import annotations

import asyncio

import httpx

from src.settings import get_settings


async def _run() -> None:
    settings = get_settings()
    # 0.0.0.0 is a bind address, not one to connect to (fails on Windows).
    host = "127.0.0.1" if settings.host in ("0.0.0.0", "::") else settings.host
    base_url = f"http://{host}:{settings.port}"
    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        response = await client.get("/healthz")
        response.raise_for_status()
        print(f"healthz={response.json()}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
