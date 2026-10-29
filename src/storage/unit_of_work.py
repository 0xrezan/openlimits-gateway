from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.storage.repositories.api_keys import APIKeyRepository
from src.storage.repositories.audit_logs import AuditLogRepository
from src.storage.repositories.consumers import ConsumerRepository
from src.storage.repositories.policies import PolicyRepository
from src.storage.repositories.routes import RouteRepository
from src.storage.repositories.usage import UsageRepository


class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self.consumers: ConsumerRepository
        self.api_keys: APIKeyRepository
        self.routes: RouteRepository
        self.policies: PolicyRepository
        self.audit_logs: AuditLogRepository
        self.usage: UsageRepository

    async def __aenter__(self) -> UnitOfWork:
        self.session = self._session_factory()
        self.consumers = ConsumerRepository(self.session)
        self.api_keys = APIKeyRepository(self.session)
        self.routes = RouteRepository(self.session)
        self.policies = PolicyRepository(self.session)
        self.audit_logs = AuditLogRepository(self.session)
        self.usage = UsageRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        if exc is None:
            await self.session.commit()
        else:
            await self.session.rollback()
        await self.session.close()
