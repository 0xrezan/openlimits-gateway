from __future__ import annotations

from src.policy.models import RoutePolicy


def method_allowed(policy: RoutePolicy, method: str) -> bool:
    return not policy.allowed_methods or method.upper() in policy.allowed_methods
