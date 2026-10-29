from __future__ import annotations

from pydantic import BaseModel, Field

from src.policy.models import QuotaPolicy, RateLimitPolicy, RetryPolicy


class PolicyUpsertRequest(BaseModel):
    enabled: bool = True
    allowed_methods: list[str] = Field(default_factory=list)
    allow_ip_forwarding: bool = False
    header_allowlist: list[str] = Field(default_factory=list)
    ip_allowlist: list[str] = Field(default_factory=list)
    rate_limit: RateLimitPolicy
    quotas: list[QuotaPolicy] = Field(default_factory=list)
    retries: RetryPolicy = Field(default_factory=RetryPolicy)
