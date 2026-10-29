from __future__ import annotations

REQUEST_ID_HEADER = "x-request-id"
API_KEY_HEADER = "x-api-key"
AUTHORIZATION_HEADER = "authorization"
PROXY_AUTHORIZATION_HEADER = "proxy-authorization"
UPSTREAM_SIGNING_HEADER = "x-gateway-signature"
UPSTREAM_TIMESTAMP_HEADER = "x-gateway-timestamp"
UPSTREAM_REQUEST_ID_HEADER = "x-gateway-request-id"
UPSTREAM_CONSUMER_HEADER = "x-gateway-consumer-id"
UPSTREAM_KEY_HEADER = "x-gateway-key-id"

FORWARDED_HEADERS_TO_STRIP = {
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-forwarded-port",
    "x-real-ip",
    "via",
    "cf-connecting-ip",
    "true-client-ip",
}

SENSITIVE_HEADERS = {
    AUTHORIZATION_HEADER,
    PROXY_AUTHORIZATION_HEADER,
    API_KEY_HEADER,
    "x-auth-token",
    "cookie",
    "set-cookie",
}

DEFAULT_REQUEST_HEADER_ALLOWLIST = {
    "accept",
    "accept-encoding",
    "cache-control",
    "content-length",
    "content-type",
    "if-match",
    "if-none-match",
    "if-modified-since",
    "user-agent",
}

DEFAULT_RESPONSE_HEADER_ALLOWLIST = {
    "cache-control",
    "content-length",
    "content-type",
    "etag",
    "last-modified",
}

EXEMPT_PATH_PREFIXES = (
    "/healthz",
    "/readyz",
    "/metrics",
    "/admin",
)
