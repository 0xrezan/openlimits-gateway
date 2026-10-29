from __future__ import annotations

import pytest

from src.core.exceptions import RateLimitExceededError
from src.limits.rate_limiter import AuthFailureLimiter
from src.tests.fixtures.fakes import FakeCounterBackend


@pytest.mark.asyncio
async def test_auth_failure_limiter_blocks_after_threshold() -> None:
    limiter = AuthFailureLimiter(FakeCounterBackend({}))
    await limiter.check(client_identifier="127.0.0.1", requests=2, window_seconds=60)
    await limiter.record_failure(client_identifier="127.0.0.1", requests=2, window_seconds=60)
    await limiter.check(client_identifier="127.0.0.1", requests=2, window_seconds=60)
    await limiter.record_failure(client_identifier="127.0.0.1", requests=2, window_seconds=60)
    with pytest.raises(RateLimitExceededError):
        await limiter.check(client_identifier="127.0.0.1", requests=2, window_seconds=60)


@pytest.mark.asyncio
async def test_auth_failure_limiter_reset_clears_current_window() -> None:
    limiter = AuthFailureLimiter(FakeCounterBackend({}))
    await limiter.record_failure(client_identifier="127.0.0.1", requests=2, window_seconds=60)
    await limiter.reset(client_identifier="127.0.0.1", window_seconds=60)
    await limiter.check(client_identifier="127.0.0.1", requests=1, window_seconds=60)
