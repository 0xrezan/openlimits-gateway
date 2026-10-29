# OpenLimits Gateway

[![CI](https://github.com/0xrezan/openlimits-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/0xrezan/openlimits-gateway/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A multi-tenant API gateway for a VPS edge. Give each client their own API key, quotas, and rate limits, and relay their traffic to a private backend (an LLM service, for example) without exposing who they are or what credentials the backend uses.

Clients authenticate with per-user keys that never leave the gateway. Upstream sees one gateway-owned identity: a service token plus an optional HMAC signature or mTLS. Streaming (SSE / chunked) responses pass through untouched.

## Runtime Flow

```mermaid
flowchart LR
    C[Client<br/>x-api-key] --> A[Authenticate<br/>hashed key lookup]
    A --> Z[Authorize<br/>route policy]
    Z --> L[Limit<br/>Redis rate + quota]
    L --> S[Sanitize<br/>drop identity headers]
    S --> G[Sign<br/>service token, HMAC, mTLS]
    G --> R[Relay<br/>retries, timeouts,<br/>circuit breaker]
    R --> U[(Private upstream)]
    R --> O[Observe<br/>metrics, traces,<br/>audit log]
```

The gateway takes architectural cues from:

- Kong and APISIX: consumer/key primitives, route-attached policy, plugin-style request handling.
- Ory Oathkeeper: explicit separation of authentication, authorization, and mutation/sanitization.
- Envoy: resilience around timeouts, retries, circuit breakers, and bulkheads.
- KrakenD and Traefik: declarative routing configuration and operational ergonomics.
- Tyk: per-key quotas, lifecycle controls, and admin-plane concerns.

## Features

- FastAPI/Starlette async gateway with one shared `httpx.AsyncClient`
- PostgreSQL persistence for consumers, API keys, policies, routes, usage, and audit logs
- Redis-backed rate limits and quotas
- Header sanitization with allowlist-based forwarding
- Upstream service identity injection with bearer token and optional HMAC signing
- Optional mTLS upstream support
- Config-driven routing and policy registry with last-known-good reload
- Prometheus metrics, OpenTelemetry instrumentation, and structured logs
- APScheduler worker for quota resets, expired-key cleanup, cache warmup, and retention cleanup
- Admin API for consumer and route management
- Standalone `diagnostic.py` for readiness checks

## Quick Start

1. Copy `.env.example` to `.env` and fill in secrets.
2. Start dependencies:

```bash
docker compose -f deploy/docker-compose.yml up -d postgres redis
```

3. Install dependencies and run migrations:

```bash
pip install -r requirements-dev.txt
alembic upgrade head
```

4. Start the API:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

5. Start the worker:

```bash
python -m src.workers.scheduler
```

6. Run diagnostics:

```bash
python diagnostic.py
```

## Public Endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `/{path:path}` for routed relay traffic

## Admin Endpoints

Admin routes live under `/admin` and are disabled by default unless `GATEWAY_ADMIN_API_ENABLED=true`.

## Security Assumptions

- `main` should trust the gateway-managed upstream token / HMAC signature; network restriction to only the VPS is optional and deployment-specific.
- User API keys are only validated at the gateway and are never forwarded upstream.
- Forwarding headers such as `X-Forwarded-For`, `Forwarded`, `Via`, and `X-Real-IP` are dropped unless an explicit route policy allows a replacement.
- All config is validated before activation; hot reload is atomic and keeps a last-known-good snapshot.

## Helpful Scripts

- `python scripts/hash_admin_token.py` to generate `GATEWAY_ADMIN_API_TOKEN_HASH`
- `python scripts/create_consumer.py <name> --issue-key`
- `python scripts/lint_config.py`
- `python scripts/smoke_test.py`
- `python -m uvicorn scripts.mock_upstream:app --host 127.0.0.1 --port 18080`
- `python scripts/stub_relay_test.py --api-key <issued-key>`

## Stub Testing

You can test the gateway without a real `main` backend by pointing `GATEWAY_UPSTREAM_BASE_URL`
to a local mock upstream.

1. Start PostgreSQL and Redis:

```bash
docker compose -f deploy/docker-compose.yml up -d postgres redis
```

2. Set these values in `.env`:

```bash
GATEWAY_DATABASE_URL=postgresql+asyncpg://gateway:gateway@127.0.0.1:5432/gateway
GATEWAY_REDIS_URL=redis://127.0.0.1:6379/0
GATEWAY_UPSTREAM_BASE_URL=http://127.0.0.1:18080
GATEWAY_UPSTREAM_SERVICE_TOKEN=stub-service-token
GATEWAY_UPSTREAM_SIGNING_KEY=stub-signing-key
```

3. Run migrations and start the mock upstream:

```bash
alembic upgrade head
python -m uvicorn scripts.mock_upstream:app --host 127.0.0.1 --port 18080
```

4. Start the gateway, create a consumer, and run the stub relay test:

```bash
uvicorn src.main:app --host 127.0.0.1 --port 8080
python scripts/create_consumer.py demo --issue-key
python scripts/stub_relay_test.py --api-key <issued-key>
```

The stub test verifies that the user API key and forwarding headers do not reach
upstream, while the gateway-owned upstream identity headers do.

To test streaming/SSE through the same stub upstream:

```bash
curl -N -H "x-api-key: <issued-key>" http://127.0.0.1:8080/api/sse
```

## Debug HTTP Logging

Set these env vars in `.env` to enable safe request/response tracing between the
gateway and upstream `main`:

```bash
GATEWAY_ENABLE_DEBUG_HTTP_LOGS=true
GATEWAY_DEBUG_HTTP_LOG_MAX_REQUEST_BODY_BYTES=8192
GATEWAY_DEBUG_HTTP_LOG_MAX_RESPONSE_BODY_BYTES=8192
GATEWAY_DEBUG_HTTP_LOG_MAX_STREAM_CHUNK_PREVIEWS=3
GATEWAY_UPSTREAM_STREAM_TRANSPORT_MODE=auto
```

`GATEWAY_UPSTREAM_STREAM_TRANSPORT_MODE` supports:

- `auto`: stream transport only when the request explicitly looks like streaming
  (`"stream": true`, `Accept: text/event-stream`, or `?stream=true`)
- `always`: always use upstream stream transport
- `never`: never use upstream stream transport

When enabled, the gateway emits structured JSON events:

- `relay_request_received`
- `upstream_request_sent`
- `upstream_response_received`
- `relay_response_sent`
- `relay_error`

Secrets are redacted in headers and JSON bodies. For example:

- `Authorization: Bearer ***redacted***`
- `x-api-key: gk_***redacted***`
- JSON fields like `api_key`, `token`, `secret`, `password`, `session_id`

### What Gets Logged

- Final upstream URL, method, query string, and sanitized headers
- Request and response body previews with truncation limits
- Top-level `model` field when present in JSON payloads
- Consumer and key identifiers from the authenticated gateway principal
- Retry attempts, timeout kinds, network errors, and upstream disconnects
- Streaming metadata for SSE/chunked responses:
  first chunk timing, total bytes, and first chunk previews

### Watching Logs

With Docker:

```bash
docker logs -f <gateway-container> | jq -c .
```

With systemd:

```bash
journalctl -u gateway.service -f | jq -c .
```

To a file:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080 >> gateway.jsonl 2>&1
tail -f gateway.jsonl | jq -c .
```

### Example Trace

```json
{
  "event": "upstream_request_sent",
  "timestamp": "2026-03-15T12:34:56.123456Z",
  "request_id": "req-9d1f0d5b",
  "consumer_name": "alice",
  "key_prefix": "demo",
  "route_code": "default-api",
  "method": "POST",
  "upstream_url": "https://main.internal/v1/chat/completions",
  "query_string": "",
  "sanitized_headers": {
    "authorization": "Bearer ***redacted***",
    "content-type": "application/json",
    "x-request-id": "req-9d1f0d5b"
  },
  "content_type": "application/json",
  "content_length": 128,
  "model": "gpt-5",
  "body_json": {
    "model": "gpt-5",
    "messages": [{"role": "user", "content": "hello"}]
  },
  "preparation_ms": 1.42,
  "request_streaming": false
}
```

## Developer Commands

```bash
ruff check .
mypy src
pytest
python scripts/lint_config.py
python scripts/smoke_test.py
```

## License

[MIT](LICENSE)
