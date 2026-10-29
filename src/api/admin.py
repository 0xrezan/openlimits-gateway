from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from src.auth.admin_auth import require_admin_token
from src.core.enums import AuditActorType, AuditEventType, ConsumerStatus
from src.observability.events import AuditEvent
from src.schemas.admin import ReloadConfigResponse
from src.schemas.api_key import APIKeyIssueRequest, APIKeyIssueResponse
from src.schemas.consumer import ConsumerCreateRequest, ConsumerResponse
from src.schemas.policy import PolicyUpsertRequest
from src.schemas.route import RouteUpsertRequest

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml_atomically(path: Path, data: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    tmp_path.replace(path)


async def _record_admin_event(request: Request, event: AuditEvent) -> None:
    await request.app.state.container.audit_service.record(event)


@router.post("/consumers", response_model=ConsumerResponse)
async def create_consumer(payload: ConsumerCreateRequest, request: Request) -> ConsumerResponse:
    container = request.app.state.container
    try:
        async with container.uow() as uow:
            consumer = await uow.consumers.create(
                name=payload.name,
                description=payload.description,
                allowed_ips=payload.allowed_ips,
                metadata_json=payload.metadata,
            )
    except IntegrityError as error:
        raise HTTPException(status_code=409, detail="consumer already exists") from error
    await _record_admin_event(
        request,
        AuditEvent(
            actor_type=AuditActorType.ADMIN,
            event_type=AuditEventType.CONSUMER_CREATED,
            resource_type="consumer",
            resource_id=str(consumer.id),
            detail={"name": consumer.name},
        ),
    )
    return ConsumerResponse(
        id=consumer.id,
        name=consumer.name,
        description=consumer.description,
        status=consumer.status,
        allowed_ips=consumer.allowed_ips,
        metadata=consumer.metadata_json,
        created_at=consumer.created_at,
    )


@router.post("/consumers/{consumer_id}/keys", response_model=APIKeyIssueResponse)
async def issue_api_key(
    consumer_id: UUID,
    payload: APIKeyIssueRequest,
    request: Request,
) -> APIKeyIssueResponse:
    container = request.app.state.container
    async with container.uow() as uow:
        consumer = await uow.consumers.get(consumer_id)
        if consumer is None:
            raise HTTPException(status_code=404, detail="consumer not found")
        issued = await container.key_service.issue_key(
            uow,
            consumer_id=consumer_id,
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
        )
    await _record_admin_event(
        request,
        AuditEvent(
            actor_type=AuditActorType.ADMIN,
            event_type=AuditEventType.KEY_ISSUED,
            resource_type="api_key",
            resource_id=str(issued.key_id),
            detail={"consumer_id": str(consumer_id), "prefix": issued.key_prefix},
        ),
    )
    return APIKeyIssueResponse(
        key_id=issued.key_id,
        key_prefix=issued.key_prefix,
        api_key=issued.api_key,
        last_four=issued.last_four,
    )


@router.post("/keys/{key_id}/revoke")
async def revoke_api_key(key_id: UUID, request: Request) -> dict[str, str]:
    container = request.app.state.container
    async with container.uow() as uow:
        api_key = await uow.api_keys.revoke(key_id)
        if api_key is None:
            raise HTTPException(status_code=404, detail="api key not found")
        await container.consumer_cache.invalidate(api_key.prefix)
    await _record_admin_event(
        request,
        AuditEvent(
            actor_type=AuditActorType.ADMIN,
            event_type=AuditEventType.KEY_REVOKED,
            resource_type="api_key",
            resource_id=str(key_id),
            detail={},
        ),
    )
    return {"status": "revoked"}


@router.post("/consumers/{consumer_id}/disable")
async def disable_consumer(consumer_id: UUID, request: Request) -> dict[str, str]:
    container = request.app.state.container
    async with container.uow() as uow:
        consumer = await uow.consumers.get(consumer_id)
        if consumer is None:
            raise HTTPException(status_code=404, detail="consumer not found")
        consumer.status = ConsumerStatus.DISABLED.value
    await _record_admin_event(
        request,
        AuditEvent(
            actor_type=AuditActorType.ADMIN,
            event_type=AuditEventType.CONSUMER_DISABLED,
            resource_type="consumer",
            resource_id=str(consumer_id),
            detail={},
        ),
    )
    return {"status": "disabled"}


@router.get("/consumers/{consumer_id}/usage")
async def list_consumer_usage(consumer_id: UUID, request: Request) -> list[dict[str, Any]]:
    container = request.app.state.container
    async with container.uow() as uow:
        usage_rows = await uow.usage.list_recent_for_consumer(consumer_id)
    return [
        {
            "route_code": row.route_code,
            "bucket_start": row.bucket_start.isoformat(),
            "bucket_granularity": row.bucket_granularity,
            "request_count": row.request_count,
            "success_count": row.success_count,
            "error_count": row.error_count,
            "bytes_in": row.bytes_in,
            "bytes_out": row.bytes_out,
        }
        for row in usage_rows
    ]


@router.put("/routes/{code}")
async def update_route(code: str, payload: RouteUpsertRequest, request: Request) -> dict[str, str]:
    container = request.app.state.container
    config_path = container.settings.route_config
    original = _read_yaml(config_path)
    updated = dict(original)
    routes = list(updated.get("routes", []))
    route_payload = payload.model_dump(mode="json")
    route_payload["code"] = code
    replaced = False
    for index, route in enumerate(routes):
        if route.get("code") == code:
            routes[index] = route_payload
            replaced = True
            break
    if not replaced:
        routes.append(route_payload)
    updated["routes"] = routes
    try:
        _write_yaml_atomically(config_path, updated)
        container.config_watcher.reload_if_changed()
        await container.sync_runtime_config_to_db()
    except Exception:
        _write_yaml_atomically(config_path, original)
        raise
    await _record_admin_event(
        request,
        AuditEvent(
            actor_type=AuditActorType.ADMIN,
            event_type=AuditEventType.ROUTE_UPDATED,
            resource_type="route",
            resource_id=code,
            detail=route_payload,
        ),
    )
    return {"status": "updated"}


@router.put("/policies/{code}")
async def update_policy(
    code: str, payload: PolicyUpsertRequest, request: Request
) -> dict[str, str]:
    container = request.app.state.container
    config_path = container.settings.policy_config
    original = _read_yaml(config_path)
    updated = dict(original)
    policies = list(updated.get("policies", []))
    policy_payload = payload.model_dump(mode="json")
    policy_payload["code"] = code
    replaced = False
    for index, policy in enumerate(policies):
        if policy.get("code") == code:
            policies[index] = policy_payload
            replaced = True
            break
    if not replaced:
        policies.append(policy_payload)
    updated["policies"] = policies
    try:
        _write_yaml_atomically(config_path, updated)
        container.config_watcher.reload_if_changed()
        await container.sync_runtime_config_to_db()
    except Exception:
        _write_yaml_atomically(config_path, original)
        raise
    await _record_admin_event(
        request,
        AuditEvent(
            actor_type=AuditActorType.ADMIN,
            event_type=AuditEventType.POLICY_UPDATED,
            resource_type="policy",
            resource_id=code,
            detail=policy_payload,
        ),
    )
    return {"status": "updated"}


@router.post("/config/reload", response_model=ReloadConfigResponse)
async def reload_config(request: Request) -> ReloadConfigResponse:
    container = request.app.state.container
    reloaded = container.config_watcher.reload_if_changed()
    if reloaded:
        await container.sync_runtime_config_to_db()
    return ReloadConfigResponse(reloaded=reloaded)
