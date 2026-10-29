from __future__ import annotations

from src.core.exceptions import ConfigValidationError
from src.policy.models import PolicyFile
from src.routes.schema import RouteFile


def validate_route_file(route_file: RouteFile) -> None:
    codes = [route.code for route in route_file.routes]
    if len(codes) != len(set(codes)):
        raise ConfigValidationError("duplicate route code found in routes.yaml")


def validate_policy_file(policy_file: PolicyFile) -> None:
    codes = [policy.code for policy in policy_file.policies]
    if len(codes) != len(set(codes)):
        raise ConfigValidationError("duplicate policy code found in policies.yaml")
