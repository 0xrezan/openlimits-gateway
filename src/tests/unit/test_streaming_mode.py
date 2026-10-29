from __future__ import annotations

from starlette.requests import Request

from src.proxy.streaming import request_expects_streaming


def make_request(
    *,
    accept: str | None = None,
    query_string: bytes = b"",
    content_type: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if accept is not None:
        headers.append((b"accept", accept.encode()))
    if content_type is not None:
        headers.append((b"content-type", content_type.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/test",
        "query_string": query_string,
        "headers": headers,
    }
    return Request(scope)


def test_request_expects_streaming_for_json_stream_true() -> None:
    request = make_request(content_type="application/json")
    assert request_expects_streaming(request, b'{"stream": true, "model": "gpt-5"}') is True


def test_request_expects_streaming_for_sse_accept_header() -> None:
    request = make_request(accept="text/event-stream")
    assert request_expects_streaming(request, b"") is True


def test_request_expects_streaming_false_by_default() -> None:
    request = make_request(content_type="application/json")
    assert request_expects_streaming(request, b'{"stream": false, "model": "gpt-5"}') is False
