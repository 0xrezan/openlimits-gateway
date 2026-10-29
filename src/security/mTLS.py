from __future__ import annotations

import ssl

from src.settings import Settings


def build_ssl_context(settings: Settings) -> ssl.SSLContext | None:
    if not settings.upstream_mtls_enabled:
        return None
    context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile=str(settings.upstream_ca_cert) if settings.upstream_ca_cert else None,
    )
    if settings.upstream_client_cert and settings.upstream_client_key:
        context.load_cert_chain(
            certfile=str(settings.upstream_client_cert),
            keyfile=str(settings.upstream_client_key),
        )
    return context
