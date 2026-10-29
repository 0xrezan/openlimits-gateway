from __future__ import annotations

from src.core.constants import REQUEST_ID_HEADER, UPSTREAM_CONSUMER_HEADER, UPSTREAM_KEY_HEADER
from src.core.context import RequestContext
from src.security.secrets import require_secret
from src.security.signing import sign_payload
from src.settings import Settings


def build_upstream_identity_headers(
    *,
    settings: Settings,
    context: RequestContext,
    method: str,
    path_with_query: str,
    body: bytes,
) -> dict[str, str]:
    headers = {
        settings.upstream_service_token_header: (
            f"Bearer {require_secret(settings.upstream_service_token, 'upstream_service_token')}"
        ),
        REQUEST_ID_HEADER: context.request_id,
    }
    if context.consumer_id is not None:
        headers[UPSTREAM_CONSUMER_HEADER] = str(context.consumer_id)
    if context.key_id is not None:
        headers[UPSTREAM_KEY_HEADER] = str(context.key_id)
    if settings.upstream_signing_enabled and settings.upstream_signing_key is not None:
        headers.update(
            sign_payload(
                secret=require_secret(settings.upstream_signing_key, "upstream_signing_key"),
                method=method,
                path_with_query=path_with_query,
                body=body,
                request_id=context.request_id,
            )
        )
    return headers
