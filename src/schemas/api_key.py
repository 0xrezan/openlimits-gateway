from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class APIKeyIssueRequest(BaseModel):
    name: str
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class APIKeyIssueResponse(BaseModel):
    key_id: UUID
    key_prefix: str
    api_key: str
    last_four: str


class APIKeyResponse(BaseModel):
    id: UUID
    name: str
    prefix: str
    last_four: str
    scopes: list[str]
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
