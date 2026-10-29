from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from time import monotonic
from uuid import UUID


@dataclass(slots=True)
class RequestContext:
    request_id: str
    started_at: float = field(default_factory=monotonic)
    consumer_id: UUID | None = None
    consumer_name: str | None = None
    key_id: UUID | None = None
    key_name: str | None = None
    key_prefix: str | None = None
    route_id: str | None = None
    route_code: str | None = None
    client_host: str | None = None


_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(context: RequestContext) -> None:
    _request_context.set(context)


def get_request_context() -> RequestContext | None:
    return _request_context.get()


def clear_request_context() -> None:
    _request_context.set(None)
