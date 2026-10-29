"""Initial gateway schema."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260314_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consumers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("allowed_ips", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consumers_name"), "consumers", ["name"], unique=True)
    op.create_index(op.f("ix_consumers_status"), "consumers", ["status"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consumer_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("last_four", sa.String(length=4), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["consumer_id"], ["consumers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_keys_consumer_id"), "api_keys", ["consumer_id"], unique=False)
    op.create_index(op.f("ix_api_keys_prefix"), "api_keys", ["prefix"], unique=True)

    op.create_table(
        "routes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("public_path_prefix", sa.String(length=255), nullable=False),
        sa.Column("upstream_path_prefix", sa.String(length=255), nullable=False),
        sa.Column("allowed_methods", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("policy_code", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("timeout_ms", sa.Integer(), nullable=False),
        sa.Column("config_source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_routes_code"), "routes", ["code"], unique=True)

    op.create_table(
        "policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config_source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_policies_code"), "policies", ["code"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_logs_event_type"), "audit_logs", ["event_type"], unique=False)

    op.create_table(
        "usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("consumer_id", sa.Uuid(), nullable=False),
        sa.Column("key_id", sa.Uuid(), nullable=False),
        sa.Column("route_code", sa.String(length=120), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bucket_granularity", sa.String(length=32), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("bytes_in", sa.Integer(), nullable=False),
        sa.Column("bytes_out", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["consumer_id"], ["consumers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "consumer_id",
            "key_id",
            "route_code",
            "bucket_start",
            "bucket_granularity",
            name="uq_usage_bucket",
        ),
    )
    op.create_index(op.f("ix_usage_bucket_start"), "usage", ["bucket_start"], unique=False)
    op.create_index(op.f("ix_usage_consumer_id"), "usage", ["consumer_id"], unique=False)
    op.create_index(op.f("ix_usage_key_id"), "usage", ["key_id"], unique=False)
    op.create_index(op.f("ix_usage_route_code"), "usage", ["route_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_route_code"), table_name="usage")
    op.drop_index(op.f("ix_usage_key_id"), table_name="usage")
    op.drop_index(op.f("ix_usage_consumer_id"), table_name="usage")
    op.drop_index(op.f("ix_usage_bucket_start"), table_name="usage")
    op.drop_table("usage")
    op.drop_index(op.f("ix_audit_logs_event_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_policies_code"), table_name="policies")
    op.drop_table("policies")
    op.drop_index(op.f("ix_routes_code"), table_name="routes")
    op.drop_table("routes")
    op.drop_index(op.f("ix_api_keys_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_consumer_id"), table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index(op.f("ix_consumers_status"), table_name="consumers")
    op.drop_index(op.f("ix_consumers_name"), table_name="consumers")
    op.drop_table("consumers")
