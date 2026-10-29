from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request, Response

from src.auth.service_identity import build_upstream_identity_headers
from src.bootstrap import GatewayContainer
from src.core.exceptions import GatewayError

router = APIRouter(include_in_schema=False)


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def relay(request: Request, path: str) -> Response:
    del path
    container = cast(GatewayContainer, request.app.state.container)
    route_resolution = request.state.route_resolution
    decision = request.state.policy_decision
    context = request.state.request_context
    principal = request.state.principal
    body = await request.body()
    container.debug_http_logger.log_relay_request_received(
        request=request,
        context=context,
        principal=principal,
        route_resolution=route_resolution,
        body=body,
    )
    path_with_query = route_resolution.upstream_path
    if request.url.query:
        path_with_query = f"{path_with_query}?{request.url.query}"
    identity_headers = build_upstream_identity_headers(
        settings=container.settings,
        context=context,
        method=request.method,
        path_with_query=path_with_query,
        body=body,
    )
    try:
        relay_result = await container.relay_service.relay(
            request=request,
            route_resolution=route_resolution,
            context=context,
            allowed_headers=decision.header_allowlist,
            identity_headers=identity_headers,
            body=body,
        )
    except GatewayError:
        async with container.uow() as uow:
            await uow.usage.record(
                consumer_id=principal.consumer_id,
                key_id=principal.key_id,
                route_code=route_resolution.route.code,
                success=False,
                bytes_in=len(body),
                bytes_out=0,
            )
        raise
    async with container.uow() as uow:
        await uow.usage.record(
            consumer_id=principal.consumer_id,
            key_id=principal.key_id,
            route_code=route_resolution.route.code,
            success=relay_result.status_code < 500,
            bytes_in=relay_result.bytes_in,
            bytes_out=relay_result.bytes_out,
        )
    return relay_result.response
