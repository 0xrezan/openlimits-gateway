from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConsumerCreateRequest(BaseModel):
    name: str
    description: str | None = None
    allowed_ips: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class ConsumerResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    allowed_ips: list[str]
    metadata: dict[str, object]
    created_at: datetime
