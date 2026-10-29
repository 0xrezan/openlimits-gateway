from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RetryConfig(BaseModel):
    enabled: bool = True
    attempts: int = 2
    retryable_methods: list[str] = Field(default_factory=lambda: ["GET", "HEAD"])
    retry_on_statuses: list[int] = Field(default_factory=lambda: [502, 503, 504])
    base_delay_ms: int = 100
    max_delay_ms: int = 1_000
    jitter_ms: int = 100

    @field_validator("retryable_methods")
    @classmethod
    def _upper_methods(cls, value: list[str]) -> list[str]:
        return [method.upper() for method in value]


class CircuitBreakerConfig(BaseModel):
    enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout_seconds: int = 30
    half_open_max_requests: int = 2


class BulkheadConfig(BaseModel):
    max_concurrency: int = 100


class ForwardingConfig(BaseModel):
    request_headers: list[str] = Field(default_factory=list)
    response_headers: list[str] = Field(default_factory=list)


class RouteConfig(BaseModel):
    code: str
    public_path_prefix: str
    upstream_path_prefix: str
    methods: list[str]
    policy_code: str
    enabled: bool = True
    timeout_ms: int = 30_000
    retry: RetryConfig = Field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    bulkhead: BulkheadConfig = Field(default_factory=BulkheadConfig)
    forwarding: ForwardingConfig = Field(default_factory=ForwardingConfig)

    @field_validator("methods")
    @classmethod
    def _normalize_methods(cls, value: list[str]) -> list[str]:
        normalized = [method.upper() for method in value]
        if not normalized:
            raise ValueError("route methods must not be empty")
        return normalized

    @field_validator("public_path_prefix", "upstream_path_prefix")
    @classmethod
    def _normalize_prefixes(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("path prefixes must start with /")
        return value.rstrip("/") + "/"


class RouteFile(BaseModel):
    version: int = 1
    routes: list[RouteConfig]
