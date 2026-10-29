from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.auth.consumer_cache import CachedPrincipal, ConsumerCache
from src.auth.hashing import hash_api_key, verify_api_key
from src.core.enums import ConsumerStatus
from src.core.exceptions import AuthenticationError
from src.storage.unit_of_work import UnitOfWork


@dataclass(slots=True)
class IssuedAPIKey:
    key_id: UUID
    key_prefix: str
    api_key: str
    last_four: str


@dataclass(slots=True)
class AuthenticatedPrincipal:
    consumer_id: UUID
    consumer_name: str
    consumer_status: str
    consumer_allowed_ips: list[str]
    key_id: UUID
    key_name: str
    key_prefix: str
    scopes: list[str]


class APIKeyService:
    def __init__(self, consumer_cache: ConsumerCache) -> None:
        self._consumer_cache = consumer_cache

    @staticmethod
    def _generate_parts() -> tuple[str, str]:
        return secrets.token_urlsafe(6).lower(), secrets.token_urlsafe(24)

    @staticmethod
    def parse_presented_key(presented_key: str) -> tuple[str, str]:
        prefix_tag = "gk_"
        if not presented_key.startswith(prefix_tag):
            raise AuthenticationError("invalid api key format")
        remainder = presented_key[len(prefix_tag) :]
        try:
            prefix, secret = remainder.split("_", 1)
        except ValueError as error:
            raise AuthenticationError("invalid api key format") from error
        if not prefix or not secret:
            raise AuthenticationError("invalid api key format")
        return prefix, secret

    async def issue_key(
        self,
        uow: UnitOfWork,
        *,
        consumer_id: UUID,
        name: str,
        scopes: list[str],
        expires_at: datetime | None,
    ) -> IssuedAPIKey:
        prefix, secret = self._generate_parts()
        raw_key = f"gk_{prefix}_{secret}"
        api_key = await uow.api_keys.create(
            consumer_id=consumer_id,
            name=name,
            prefix=prefix,
            last_four=secret[-4:],
            key_hash=hash_api_key(raw_key),
            scopes=scopes,
            expires_at=expires_at,
        )
        return IssuedAPIKey(
            key_id=api_key.id,
            key_prefix=prefix,
            api_key=raw_key,
            last_four=secret[-4:],
        )

    async def authenticate(self, uow: UnitOfWork, presented_key: str) -> AuthenticatedPrincipal:
        prefix, _ = self.parse_presented_key(presented_key)
        cached = await self._consumer_cache.get(prefix)
        if cached is not None and verify_api_key(presented_key, cached.key_hash):
            if cached.revoked_at() is not None:
                raise AuthenticationError("api key revoked")
            expires_at = cached.expires_at()
            if expires_at is not None and expires_at < datetime.now(UTC):
                raise AuthenticationError("api key expired")
            if cached.consumer_status != ConsumerStatus.ACTIVE.value:
                raise AuthenticationError("consumer disabled")
            return self._principal_from_cache(cached)

        api_key = await uow.api_keys.get_with_consumer_by_prefix(prefix)
        if api_key is None:
            raise AuthenticationError()
        if not verify_api_key(presented_key, api_key.key_hash):
            raise AuthenticationError()
        if api_key.revoked_at is not None:
            raise AuthenticationError("api key revoked")
        if api_key.expires_at is not None and api_key.expires_at < datetime.now(UTC):
            raise AuthenticationError("api key expired")
        if api_key.consumer.status != ConsumerStatus.ACTIVE.value:
            raise AuthenticationError("consumer disabled")
        cached_principal = ConsumerCache.from_orm(
            consumer_id=api_key.consumer.id,
            consumer_name=api_key.consumer.name,
            consumer_status=api_key.consumer.status,
            consumer_allowed_ips=api_key.consumer.allowed_ips,
            key_id=api_key.id,
            key_name=api_key.name,
            key_hash=api_key.key_hash,
            key_prefix=api_key.prefix,
            key_expires_at=api_key.expires_at,
            key_revoked_at=api_key.revoked_at,
            scopes=api_key.scopes,
        )
        await self._consumer_cache.set(cached_principal)
        await uow.api_keys.touch_last_used(api_key)
        return self._principal_from_cache(cached_principal)

    @staticmethod
    def _principal_from_cache(cached: CachedPrincipal) -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            consumer_id=UUID(cached.consumer_id),
            consumer_name=cached.consumer_name,
            consumer_status=cached.consumer_status,
            consumer_allowed_ips=list(cached.consumer_allowed_ips),
            key_id=UUID(cached.key_id),
            key_name=cached.key_name,
            key_prefix=cached.key_prefix,
            scopes=list(cached.scopes),
        )
