from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.enums import ConsumerStatus


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(AsyncAttrs, DeclarativeBase):
    type_annotation_map: ClassVar[dict[object, object]] = {dict[str, Any]: JSONB}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Consumer(TimestampMixin, Base):
    __tablename__ = "consumers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ConsumerStatus.ACTIVE.value, index=True)
    allowed_ips: Mapped[list[str]] = mapped_column(JSONB, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    api_keys: Mapped[list[APIKey]] = relationship(back_populates="consumer")
    usages: Mapped[list[Usage]] = relationship(back_populates="consumer")


class APIKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    consumer_id: Mapped[UUID] = mapped_column(
        ForeignKey("consumers.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    last_four: Mapped[str] = mapped_column(String(4))
    key_hash: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    consumer: Mapped[Consumer] = relationship(back_populates="api_keys")
    usages: Mapped[list[Usage]] = relationship(back_populates="api_key")


class Route(TimestampMixin, Base):
    __tablename__ = "routes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    public_path_prefix: Mapped[str] = mapped_column(String(255))
    upstream_path_prefix: Mapped[str] = mapped_column(String(255))
    allowed_methods: Mapped[list[str]] = mapped_column(JSONB, default=list)
    policy_code: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=30_000)
    config_source: Mapped[str] = mapped_column(String(32), default="yaml")


class Policy(TimestampMixin, Base):
    __tablename__ = "policies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    config_source: Mapped[str] = mapped_column(String(32), default="yaml")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class Usage(TimestampMixin, Base):
    __tablename__ = "usage"
    __table_args__ = (
        UniqueConstraint(
            "consumer_id",
            "key_id",
            "route_code",
            "bucket_start",
            "bucket_granularity",
            name="uq_usage_bucket",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    consumer_id: Mapped[UUID] = mapped_column(
        ForeignKey("consumers.id", ondelete="CASCADE"), index=True
    )
    key_id: Mapped[UUID] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"), index=True)
    route_code: Mapped[str] = mapped_column(String(120), index=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    bucket_granularity: Mapped[str] = mapped_column(String(32))
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    bytes_in: Mapped[int] = mapped_column(Integer, default=0)
    bytes_out: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    consumer: Mapped[Consumer] = relationship(back_populates="usages")
    api_key: Mapped[APIKey] = relationship(back_populates="usages")
