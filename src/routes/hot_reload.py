from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.observability.logging import get_logger
from src.routes.loader import load_limit_file, load_policy_file, load_route_file
from src.routes.registry import RouteRegistry, build_snapshot

logger = get_logger(__name__)


@dataclass(slots=True)
class ConfigWatcher:
    route_path: Path
    policy_path: Path
    limit_path: Path
    route_registry: RouteRegistry
    last_mtimes: dict[Path, float]

    @classmethod
    def create(
        cls,
        route_path: Path,
        policy_path: Path,
        limit_path: Path,
        route_registry: RouteRegistry,
    ) -> ConfigWatcher:
        return cls(
            route_path=route_path,
            policy_path=policy_path,
            limit_path=limit_path,
            route_registry=route_registry,
            last_mtimes={
                path: path.stat().st_mtime for path in (route_path, policy_path, limit_path)
            },
        )

    def reload_if_changed(self) -> bool:
        current = {
            path: path.stat().st_mtime
            for path in (self.route_path, self.policy_path, self.limit_path)
        }
        if current == self.last_mtimes:
            return False
        snapshot = build_snapshot(
            load_route_file(self.route_path),
            load_policy_file(self.policy_path),
            load_limit_file(self.limit_path),
        )
        self.route_registry.replace(snapshot)
        self.last_mtimes = current
        logger.info("config_reloaded", files=[str(path) for path in current])
        return True
