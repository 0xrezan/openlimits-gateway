from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.core.enums import AuditActorType, AuditEventType


@dataclass(slots=True)
class AuditEvent:
    actor_type: AuditActorType
    event_type: AuditEventType
    resource_type: str
    detail: dict[str, Any]
    actor_id: str | None = None
    resource_id: str | None = None
    request_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
