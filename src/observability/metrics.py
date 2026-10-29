from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

_REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Total gateway requests",
    ["route", "method", "status_family"],
)
_AUTH_FAILURES_TOTAL = Counter(
    "gateway_auth_failures_total",
    "Authentication failures",
    ["reason"],
)
_POLICY_DENIALS_TOTAL = Counter(
    "gateway_policy_denials_total",
    "Policy denials",
    ["reason"],
)
_RATE_LIMIT_HITS_TOTAL = Counter(
    "gateway_rate_limit_hits_total",
    "Rate limit hits",
    ["route"],
)
_UPSTREAM_LATENCY_SECONDS = Histogram(
    "gateway_upstream_latency_seconds",
    "Upstream relay latency",
    ["route", "method"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
_UPSTREAM_TIMEOUTS_TOTAL = Counter(
    "gateway_upstream_timeouts_total",
    "Upstream timeout count",
    ["route"],
)
_RETRIES_TOTAL = Counter(
    "gateway_retries_total",
    "Relay retry attempts",
    ["route", "reason"],
)
_CIRCUIT_STATE = Gauge(
    "gateway_circuit_breaker_state",
    "Circuit breaker state. closed=0 half_open=0.5 open=1",
    ["route"],
)
_POOL_EXHAUSTION_TOTAL = Counter(
    "gateway_pool_exhaustion_total",
    "HTTP pool exhaustion count",
    ["route"],
)


class GatewayMetrics:
    def __init__(self) -> None:
        self.requests_total = _REQUESTS_TOTAL
        self.auth_failures_total = _AUTH_FAILURES_TOTAL
        self.policy_denials_total = _POLICY_DENIALS_TOTAL
        self.rate_limit_hits_total = _RATE_LIMIT_HITS_TOTAL
        self.upstream_latency_seconds = _UPSTREAM_LATENCY_SECONDS
        self.upstream_timeouts_total = _UPSTREAM_TIMEOUTS_TOTAL
        self.retries_total = _RETRIES_TOTAL
        self.circuit_state = _CIRCUIT_STATE
        self.pool_exhaustion_total = _POOL_EXHAUSTION_TOTAL


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
