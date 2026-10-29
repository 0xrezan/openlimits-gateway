from __future__ import annotations

from dataclasses import dataclass

from src.policy.models import PolicyDefaults, RateLimitPolicy, RetryPolicy, RoutePolicy
from src.routes.registry import ConfigSnapshot, RouteResolution
from src.routes.schema import (
    BulkheadConfig,
    CircuitBreakerConfig,
    ForwardingConfig,
    RetryConfig,
    RouteConfig,
)


@dataclass(slots=True)
class FakeCounterBackend:
    store: dict[str, int]

    async def increment(self, key: str, *, ttl_seconds: int, amount: int = 1) -> int:
        del ttl_seconds
        self.store[key] = self.store.get(key, 0) + amount
        return self.store[key]

    async def get(self, key: str) -> int:
        return self.store.get(key, 0)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


def make_route_resolution() -> RouteResolution:
    route = RouteConfig(
        code="default-api",
        public_path_prefix="/api/",
        upstream_path_prefix="/api/",
        methods=["GET", "POST"],
        policy_code="default",
        retry=RetryConfig(),
        circuit_breaker=CircuitBreakerConfig(),
        bulkhead=BulkheadConfig(),
        forwarding=ForwardingConfig(
            request_headers=["accept", "content-type"],
            response_headers=["content-type"],
        ),
    )
    policy = RoutePolicy(
        code="default",
        enabled=True,
        allowed_methods=["GET", "POST"],
        allow_ip_forwarding=False,
        header_allowlist=["accept", "content-type"],
        ip_allowlist=[],
        rate_limit=RateLimitPolicy(requests=10, window_seconds=60),
        quotas=[],
        retries=RetryPolicy(),
    )
    return RouteResolution(route=route, policy=policy, upstream_path="/api/test")


def make_snapshot() -> ConfigSnapshot:
    resolution = make_route_resolution()
    return ConfigSnapshot(
        routes={resolution.route.code: resolution.route},
        policies={resolution.policy.code: resolution.policy},
        defaults=PolicyDefaults(),
        limits={"global": {"requests": 1000, "window_seconds": 60}},
    )
