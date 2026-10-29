from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from src.policy.models import PolicyFile
from src.policy.validators import validate_policy_file, validate_route_file
from src.routes.schema import RouteFile


class LimitFile(BaseModel):
    version: int = 1
    limits: dict[str, dict[str, int]]


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def load_route_file(path: Path) -> RouteFile:
    route_file = RouteFile.model_validate(_load_yaml(path))
    validate_route_file(route_file)
    return route_file


def load_policy_file(path: Path) -> PolicyFile:
    policy_file = PolicyFile.model_validate(_load_yaml(path))
    validate_policy_file(policy_file)
    return policy_file


def load_limit_file(path: Path) -> LimitFile:
    return LimitFile.model_validate(_load_yaml(path))
