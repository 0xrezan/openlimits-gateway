from __future__ import annotations

from uuid import UUID

import pytest

from src.core.exceptions import RateLimitExceededError
from src.limits.rate_limiter import RateLimiter
from src.tests.fixtures.fakes import FakeCounterBackend


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit() -> None:
    limiter = RateLimiter(FakeCounterBackend({}))
    for _ in range(2):
        await limiter.enforce(
            consumer_id=UUID("00000000-0000-0000-0000-000000000000"),
            route_code="route",
            requests=2,
            window_seconds=60,
        )
    with pytest.raises(RateLimitExceededError):
        await limiter.enforce(
            consumer_id=UUID("00000000-0000-0000-0000-000000000000"),
            route_code="route",
            requests=2,
            window_seconds=60,
        )
