from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from contextlib import suppress
from typing import Protocol

import httpx
from fastapi import Request, Response
from starlette.responses import StreamingResponse


class StreamObserver(Protocol):
    async def on_chunk(self, chunk: bytes) -> None: ...

    async def on_complete(self) -> None: ...

    async def on_error(self, error: Exception) -> None: ...


STREAM_QUERY_TRUE_VALUES = {"1", "true", "yes", "on"}
STREAM_ACCEPT_HINTS = {"text/event-stream", "application/x-ndjson"}


def request_expects_streaming(request: Request, body: bytes) -> bool:
    accept = request.headers.get("accept", "").lower()
    if any(hint in accept for hint in STREAM_ACCEPT_HINTS):
        return True

    stream_query = request.query_params.get("stream")
    if stream_query is not None and stream_query.strip().lower() in STREAM_QUERY_TRUE_VALUES:
        return True

    content_type = request.headers.get("content-type", "").lower()
    if "json" not in content_type or not body:
        return False
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("stream") is True


def build_streaming_response(
    *,
    status_code: int,
    headers: dict[str, str],
    upstream_response: httpx.Response,
    observer: StreamObserver | None = None,
) -> Response:
    async def iter_bytes() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in upstream_response.aiter_bytes():
                if observer is not None:
                    with suppress(Exception):
                        await observer.on_chunk(chunk)
                yield chunk
        except Exception as error:
            if observer is not None:
                with suppress(Exception):
                    await observer.on_error(error)
            raise
        else:
            if observer is not None:
                with suppress(Exception):
                    await observer.on_complete()
        finally:
            await upstream_response.aclose()

    return StreamingResponse(
        iter_bytes(),
        status_code=status_code,
        headers=headers,
    )
