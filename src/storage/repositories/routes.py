from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import Route


class RouteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        code: str,
        public_path_prefix: str,
        upstream_path_prefix: str,
        allowed_methods: list[str],
        policy_code: str,
        enabled: bool,
        timeout_ms: int,
        config_source: str,
    ) -> Route:
        result = await self._session.execute(select(Route).where(Route.code == code))
        route = result.scalar_one_or_none()
        if route is None:
            route = Route(
                code=code,
                public_path_prefix=public_path_prefix,
                upstream_path_prefix=upstream_path_prefix,
                allowed_methods=allowed_methods,
                policy_code=policy_code,
                enabled=enabled,
                timeout_ms=timeout_ms,
                config_source=config_source,
            )
            self._session.add(route)
        else:
            route.public_path_prefix = public_path_prefix
            route.upstream_path_prefix = upstream_path_prefix
            route.allowed_methods = allowed_methods
            route.policy_code = policy_code
            route.enabled = enabled
            route.timeout_ms = timeout_ms
            route.config_source = config_source
        await self._session.flush()
        return route

    async def list_all(self) -> Sequence[Route]:
        result = await self._session.execute(select(Route).order_by(Route.code.asc()))
        return result.scalars().all()
