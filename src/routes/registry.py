from __future__ import annotations

from dataclasses import dataclass

from src.core.exceptions import RouteNotFoundError
from src.policy.models import PolicyDefaults, PolicyFile, RoutePolicy
from src.routes.loader import LimitFile
from src.routes.schema import RouteConfig, RouteFile


@dataclass(slots=True)
class ConfigSnapshot:
    routes: dict[str, RouteConfig]
    policies: dict[str, RoutePolicy]
    defaults: PolicyDefaults
    limits: dict[str, dict[str, int]]


@dataclass(slots=True)
class RouteResolution:
    route: RouteConfig
    policy: RoutePolicy
    upstream_path: str


class RouteRegistry:
    def __init__(self, snapshot: ConfigSnapshot) -> None:
        self._snapshot = snapshot
        self._last_known_good = snapshot

    @property
    def snapshot(self) -> ConfigSnapshot:
        return self._snapshot

    @property
    def last_known_good(self) -> ConfigSnapshot:
        return self._last_known_good

    def replace(self, snapshot: ConfigSnapshot) -> None:
        self._last_known_good = self._snapshot
        self._snapshot = snapshot

    def resolve(self, path: str, method: str) -> RouteResolution:
        route = self._match_route(path, method)
        policy = self._snapshot.policies.get(route.policy_code)
        if policy is None:
            raise RouteNotFoundError(
                f"route {route.code!r} references missing policy {route.policy_code!r}"
            )
        suffix = path[len(route.public_path_prefix.rstrip("/")) :]
        upstream_path = f"{route.upstream_path_prefix.rstrip('/')}{suffix or '/'}"
        return RouteResolution(route=route, policy=policy, upstream_path=upstream_path)

    def _match_route(self, path: str, method: str) -> RouteConfig:
        def matches_prefix(route: RouteConfig) -> bool:
            normalized = route.public_path_prefix.rstrip("/")
            return path == normalized or path.startswith(route.public_path_prefix)

        candidates = [
            route
            for route in self._snapshot.routes.values()
            if route.enabled and matches_prefix(route) and method.upper() in route.methods
        ]
        if not candidates:
            raise RouteNotFoundError()
        return max(candidates, key=lambda route: len(route.public_path_prefix))


def build_snapshot(
    route_file: RouteFile,
    policy_file: PolicyFile,
    limit_file: LimitFile,
) -> ConfigSnapshot:
    return ConfigSnapshot(
        routes={route.code: route for route in route_file.routes},
        policies={policy.code: policy for policy in policy_file.policies},
        defaults=policy_file.defaults,
        limits=limit_file.limits,
    )
