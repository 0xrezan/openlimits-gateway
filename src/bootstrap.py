from __future__ import annotations

import asyncio
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.auth.consumer_cache import ConsumerCache
from src.auth.key_service import APIKeyService
from src.limits.quota_store import QuotaStore
from src.limits.rate_limiter import AuthFailureLimiter, RateLimiter
from src.limits.redis_backend import RedisCounterBackend
from src.observability.audit import AuditService
from src.observability.debug_http_logging import DebugHTTPLogger
from src.observability.logging import configure_logging
from src.observability.metrics import GatewayMetrics
from src.policy.engine import PolicyEngine
from src.proxy.bulkhead import BulkheadRegistry
from src.proxy.circuit_breaker import CircuitBreakerRegistry
from src.proxy.relay import RelayService
from src.proxy.transport import build_http_client
from src.routes.hot_reload import ConfigWatcher
from src.routes.loader import load_limit_file, load_policy_file, load_route_file
from src.routes.registry import RouteRegistry, build_snapshot
from src.settings import Settings
from src.storage.db import create_engine, create_session_factory
from src.storage.unit_of_work import UnitOfWork


@dataclass(slots=True)
class GatewayContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: Redis
    metrics: GatewayMetrics
    route_registry: RouteRegistry
    config_watcher: ConfigWatcher
    consumer_cache: ConsumerCache
    key_service: APIKeyService
    policy_engine: PolicyEngine
    rate_limiter: RateLimiter
    auth_failure_limiter: AuthFailureLimiter
    quota_store: QuotaStore
    audit_service: AuditService
    debug_http_logger: DebugHTTPLogger
    circuit_breakers: CircuitBreakerRegistry
    bulkheads: BulkheadRegistry
    relay_service: RelayService
    global_semaphore: asyncio.Semaphore

    def uow(self) -> UnitOfWork:
        return UnitOfWork(self.session_factory)

    async def sync_runtime_config_to_db(self) -> None:
        async with self.uow() as uow:
            for route in self.route_registry.snapshot.routes.values():
                await uow.routes.upsert(
                    code=route.code,
                    public_path_prefix=route.public_path_prefix,
                    upstream_path_prefix=route.upstream_path_prefix,
                    allowed_methods=route.methods,
                    policy_code=route.policy_code,
                    enabled=route.enabled,
                    timeout_ms=route.timeout_ms,
                    config_source="yaml",
                )
            for policy in self.route_registry.snapshot.policies.values():
                await uow.policies.upsert(
                    code=policy.code,
                    enabled=policy.enabled,
                    config=policy.model_dump(mode="json"),
                    config_source="yaml",
                )

    async def close(self) -> None:
        await self.relay_service.close()
        await self.redis.aclose()
        await self.engine.dispose()


async def create_container(settings: Settings) -> GatewayContainer:
    configure_logging(settings.log_level, settings.logging_config)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    metrics = GatewayMetrics()
    snapshot = build_snapshot(
        load_route_file(settings.route_config),
        load_policy_file(settings.policy_config),
        load_limit_file(settings.limit_config),
    )
    route_registry = RouteRegistry(snapshot)
    config_watcher = ConfigWatcher.create(
        settings.route_config,
        settings.policy_config,
        settings.limit_config,
        route_registry,
    )
    consumer_cache = ConsumerCache(redis, settings.consumer_cache_ttl_seconds)
    key_service = APIKeyService(consumer_cache)
    policy_engine = PolicyEngine()
    counter_backend = RedisCounterBackend(redis)
    rate_limiter = RateLimiter(counter_backend)
    auth_failure_limiter = AuthFailureLimiter(counter_backend)
    quota_store = QuotaStore(counter_backend)
    audit_service = AuditService(session_factory)
    debug_http_logger = DebugHTTPLogger(settings)
    circuit_breakers = CircuitBreakerRegistry()
    bulkheads = BulkheadRegistry()
    relay_service = RelayService(
        client=build_http_client(settings),
        settings=settings,
        metrics=metrics,
        debug_logger=debug_http_logger,
        circuit_breakers=circuit_breakers,
        bulkheads=bulkheads,
    )
    container = GatewayContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        redis=redis,
        metrics=metrics,
        route_registry=route_registry,
        config_watcher=config_watcher,
        consumer_cache=consumer_cache,
        key_service=key_service,
        policy_engine=policy_engine,
        rate_limiter=rate_limiter,
        auth_failure_limiter=auth_failure_limiter,
        quota_store=quota_store,
        audit_service=audit_service,
        debug_http_logger=debug_http_logger,
        circuit_breakers=circuit_breakers,
        bulkheads=bulkheads,
        relay_service=relay_service,
        global_semaphore=asyncio.Semaphore(settings.global_concurrency_limit),
    )
    await container.sync_runtime_config_to_db()
    return container
