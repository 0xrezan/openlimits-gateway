from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RateLimitPolicy(BaseModel):
    requests: int
    window_seconds: int


class QuotaPolicy(BaseModel):
    name: str
    requests: int
    window_seconds: int


class RetryPolicy(BaseModel):
    enabled: bool = True
    unsafe_methods_allowed: bool = False


class PolicyDefaults(BaseModel):
    require_authentication: bool = True
    strip_forwarding_headers: bool = True
    remove_user_authorization: bool = True
    allow_anonymous: bool = False
    body_limit_bytes: int = 10 * 1024 * 1024
    allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "POST"])


class RoutePolicy(BaseModel):
    code: str
    enabled: bool = True
    allowed_methods: list[str] = Field(default_factory=list)
    allow_ip_forwarding: bool = False
    header_allowlist: list[str] = Field(default_factory=list)
    ip_allowlist: list[str] = Field(default_factory=list)
    rate_limit: RateLimitPolicy
    quotas: list[QuotaPolicy] = Field(default_factory=list)
    retries: RetryPolicy = Field(default_factory=RetryPolicy)

    @field_validator("allowed_methods")
    @classmethod
    def _upper_methods(cls, value: list[str]) -> list[str]:
        return [method.upper() for method in value]


class PolicyFile(BaseModel):
    version: int = 1
    defaults: PolicyDefaults
    policies: list[RoutePolicy]
