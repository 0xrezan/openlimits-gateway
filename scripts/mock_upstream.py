from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="OpenLimits Mock Upstream", docs_url="/docs", redoc_url=None)


def _normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "mock-upstream"}


@app.api_route(
    "/api/echo",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def echo(request: Request) -> dict[str, Any]:
    body = await request.body()
    return {
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query,
        "headers": _normalized_headers(request.headers),
        "body_text": body.decode("utf-8", errors="replace"),
        "body_size": len(body),
    }


@app.get("/api/status/{status_code}")
async def status_probe(status_code: int) -> JSONResponse:
    return JSONResponse({"status_code": status_code}, status_code=status_code)


@app.get("/api/slow/{delay_seconds}")
async def slow_probe(delay_seconds: float) -> dict[str, float]:
    await asyncio.sleep(delay_seconds)
    return {"slept": delay_seconds}


@app.get("/api/sse")
async def sse_probe() -> StreamingResponse:
    async def emit_events() -> AsyncIterator[bytes]:
        for index in range(3):
            await asyncio.sleep(0.05)
            yield f"data: event-{index}\n\n".encode()

    return StreamingResponse(emit_events(), media_type="text/event-stream")
