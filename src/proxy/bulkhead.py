from __future__ import annotations

import asyncio


class BulkheadRegistry:
    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def get(self, route_code: str, max_concurrency: int) -> asyncio.Semaphore:
        semaphore = self._semaphores.get(route_code)
        if semaphore is None:
            semaphore = asyncio.Semaphore(max_concurrency)
            self._semaphores[route_code] = semaphore
        return semaphore
