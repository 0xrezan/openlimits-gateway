from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from src.core.exceptions import CircuitOpenError


@dataclass(slots=True)
class CircuitState:
    state: str = "closed"
    failures: int = 0
    opened_at: float | None = None
    half_open_inflight: int = 0


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int,
        recovery_timeout_seconds: int,
        half_open_max_requests: int,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._half_open_max_requests = half_open_max_requests
        self._state = CircuitState()

    def allow_request(self) -> None:
        now = monotonic()
        if self._state.state == "open":
            if (
                self._state.opened_at is not None
                and now - self._state.opened_at >= self._recovery_timeout_seconds
            ):
                self._state.state = "half_open"
                self._state.half_open_inflight = 0
            else:
                raise CircuitOpenError()
        if self._state.state == "half_open":
            if self._state.half_open_inflight >= self._half_open_max_requests:
                raise CircuitOpenError()
            self._state.half_open_inflight += 1

    def on_success(self) -> None:
        self._state.state = "closed"
        self._state.failures = 0
        self._state.opened_at = None
        self._state.half_open_inflight = 0

    def on_failure(self) -> None:
        self._state.failures += 1
        if self._state.failures >= self._failure_threshold:
            self._state.state = "open"
            self._state.opened_at = monotonic()
            self._state.half_open_inflight = 0
        elif self._state.state == "half_open":
            self._state.state = "open"
            self._state.opened_at = monotonic()
            self._state.half_open_inflight = 0

    @property
    def state_value(self) -> float:
        if self._state.state == "open":
            return 1.0
        if self._state.state == "half_open":
            return 0.5
        return 0.0


class CircuitBreakerRegistry:
    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(
        self,
        *,
        route_code: str,
        failure_threshold: int,
        recovery_timeout_seconds: int,
        half_open_max_requests: int,
    ) -> CircuitBreaker:
        breaker = self._breakers.get(route_code)
        if breaker is None:
            breaker = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_timeout_seconds,
                half_open_max_requests=half_open_max_requests,
            )
            self._breakers[route_code] = breaker
        return breaker
