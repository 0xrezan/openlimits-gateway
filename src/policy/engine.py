from __future__ import annotations

from dataclasses import dataclass

from src.auth.key_service import AuthenticatedPrincipal
from src.core.exceptions import AuthorizationError
from src.policy.models import RoutePolicy
from src.policy.route_policy import method_allowed
from src.routes.registry import RouteResolution
from src.security.ip_allowlist import ip_allowed


@dataclass(slots=True)
class PolicyDecision:
    route_code: str
    header_allowlist: list[str]
    body_limit_bytes: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    quotas: list[tuple[str, int, int]]


class PolicyEngine:
    def evaluate(
        self,
        *,
        route_resolution: RouteResolution,
        principal: AuthenticatedPrincipal,
        client_ip: str | None,
        method: str,
        default_body_limit_bytes: int,
    ) -> PolicyDecision:
        policy = route_resolution.policy
        self._validate_policy(
            policy=policy, principal=principal, client_ip=client_ip, method=method
        )
        return PolicyDecision(
            route_code=route_resolution.route.code,
            header_allowlist=policy.header_allowlist
            or route_resolution.route.forwarding.request_headers,
            body_limit_bytes=default_body_limit_bytes,
            rate_limit_requests=policy.rate_limit.requests,
            rate_limit_window_seconds=policy.rate_limit.window_seconds,
            quotas=[(quota.name, quota.requests, quota.window_seconds) for quota in policy.quotas],
        )

    @staticmethod
    def _validate_policy(
        *,
        policy: RoutePolicy,
        principal: AuthenticatedPrincipal,
        client_ip: str | None,
        method: str,
    ) -> None:
        if not policy.enabled:
            raise AuthorizationError("policy disabled")
        if not method_allowed(policy, method):
            raise AuthorizationError("method not allowed for policy")
        if principal.consumer_allowed_ips and not ip_allowed(
            client_ip, principal.consumer_allowed_ips
        ):
            raise AuthorizationError("consumer ip not allowed")
        if policy.ip_allowlist and not ip_allowed(client_ip, policy.ip_allowlist):
            raise AuthorizationError("policy ip not allowed")
