from __future__ import annotations

from enum import StrEnum


class ConsumerStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class APIKeyStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class AuditActorType(StrEnum):
    ADMIN = "admin"
    CONSUMER = "consumer"
    SYSTEM = "system"


class AuditEventType(StrEnum):
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    POLICY_DENY = "policy_deny"
    RATE_LIMIT_HIT = "rate_limit_hit"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    KEY_ISSUED = "key_issued"
    KEY_REVOKED = "key_revoked"
    CONSUMER_CREATED = "consumer_created"
    CONSUMER_DISABLED = "consumer_disabled"
    ROUTE_UPDATED = "route_updated"
    POLICY_UPDATED = "policy_updated"
