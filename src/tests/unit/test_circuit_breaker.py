from __future__ import annotations

import pytest

from src.core.exceptions import CircuitOpenError
from src.proxy.circuit_breaker import CircuitBreaker


def test_circuit_breaker_opens_after_failures() -> None:
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_seconds=60,
        half_open_max_requests=1,
    )
    breaker.on_failure()
    breaker.on_failure()
    with pytest.raises(CircuitOpenError):
        breaker.allow_request()
