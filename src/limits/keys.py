from __future__ import annotations


def rate_limit_key(*, consumer_id: str, route_code: str, window_bucket: int) -> str:
    return f"rate:{consumer_id}:{route_code}:{window_bucket}"


def auth_failure_key(*, client_identifier: str, window_bucket: int) -> str:
    return f"auth_fail:{client_identifier}:{window_bucket}"


def quota_key(*, consumer_id: str, route_code: str, quota_name: str, window_bucket: int) -> str:
    return f"quota:{consumer_id}:{route_code}:{quota_name}:{window_bucket}"
