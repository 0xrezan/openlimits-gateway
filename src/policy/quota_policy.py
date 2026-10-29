from __future__ import annotations

from src.policy.models import QuotaPolicy


def quota_key_name(quota: QuotaPolicy) -> str:
    return f"{quota.name}:{quota.window_seconds}"
