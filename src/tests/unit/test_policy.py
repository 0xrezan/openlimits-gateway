from __future__ import annotations

from uuid import uuid4

import pytest

from src.auth.key_service import AuthenticatedPrincipal
from src.core.exceptions import AuthorizationError
from src.policy.engine import PolicyEngine
from src.tests.fixtures.fakes import make_route_resolution


def test_policy_engine_allows_valid_request() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate(
        route_resolution=make_route_resolution(),
        principal=AuthenticatedPrincipal(
            consumer_id=uuid4(),
            consumer_name="alice",
            consumer_status="active",
            consumer_allowed_ips=[],
            key_id=uuid4(),
            key_name="default",
            key_prefix="prefix",
            scopes=[],
        ),
        client_ip="127.0.0.1",
        method="GET",
        default_body_limit_bytes=1024,
    )
    assert decision.route_code == "default-api"


def test_policy_engine_denies_disallowed_ip() -> None:
    engine = PolicyEngine()
    route_resolution = make_route_resolution()
    route_resolution.policy.ip_allowlist = ["10.0.0.0/24"]
    with pytest.raises(AuthorizationError):
        engine.evaluate(
            route_resolution=route_resolution,
            principal=AuthenticatedPrincipal(
                consumer_id=uuid4(),
                consumer_name="alice",
                consumer_status="active",
                consumer_allowed_ips=[],
                key_id=uuid4(),
                key_name="default",
                key_prefix="prefix",
                scopes=[],
            ),
            client_ip="127.0.0.1",
            method="GET",
            default_body_limit_bytes=1024,
        )
