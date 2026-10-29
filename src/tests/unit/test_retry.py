from __future__ import annotations

from src.proxy.retry import RetryPolicyContext, build_retrying


def test_retry_builder_respects_attempts() -> None:
    retrying = build_retrying(
        RetryPolicyContext(
            enabled=True,
            attempts=3,
            retry_on_statuses=[502],
            base_delay_ms=100,
            max_delay_ms=200,
        )
    )
    assert getattr(retrying.stop, "max_attempt_number", None) == 3
