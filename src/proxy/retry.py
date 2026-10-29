from __future__ import annotations

from dataclasses import dataclass

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)


class RetryableUpstreamError(Exception):
    def __init__(self, response: httpx.Response, attempt_number: int) -> None:
        super().__init__(f"retryable upstream status {response.status_code}")
        self.response = response
        self.attempt_number = attempt_number


@dataclass(slots=True)
class RetryPolicyContext:
    enabled: bool
    attempts: int
    retry_on_statuses: list[int]
    base_delay_ms: int
    max_delay_ms: int


def build_retrying(policy: RetryPolicyContext) -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(policy.attempts),
        wait=wait_random_exponential(
            multiplier=policy.base_delay_ms / 1000,
            max=policy.max_delay_ms / 1000,
        ),
        retry=retry_if_exception_type(
            (httpx.TransportError, httpx.TimeoutException, RetryableUpstreamError)
        ),
        reraise=True,
    )
