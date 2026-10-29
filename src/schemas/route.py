from __future__ import annotations

from pydantic import BaseModel, Field

from src.routes.schema import BulkheadConfig, CircuitBreakerConfig, ForwardingConfig, RetryConfig


class RouteUpsertRequest(BaseModel):
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
