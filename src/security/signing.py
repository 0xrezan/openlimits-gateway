from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

from src.core.constants import (
    UPSTREAM_REQUEST_ID_HEADER,
    UPSTREAM_SIGNING_HEADER,
    UPSTREAM_TIMESTAMP_HEADER,
)


def sign_payload(
    *,
    secret: str,
    method: str,
    path_with_query: str,
    body: bytes,
    request_id: str,
) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat()
    body_digest = hashlib.sha256(body).hexdigest()
    canonical = "\n".join([method.upper(), path_with_query, body_digest, timestamp, request_id])
    signature = hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        UPSTREAM_SIGNING_HEADER: signature,
        UPSTREAM_TIMESTAMP_HEADER: timestamp,
        UPSTREAM_REQUEST_ID_HEADER: request_id,
    }
