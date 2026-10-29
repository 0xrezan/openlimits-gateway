from __future__ import annotations

from collections.abc import Mapping


class GatewayError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.headers = dict(headers or {})


class ConfigValidationError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500, code="config_validation_error")


class AuthenticationError(GatewayError):
    def __init__(self, message: str = "authentication failed") -> None:
        super().__init__(message, status_code=401, code="authentication_failed")


class AuthorizationError(GatewayError):
    def __init__(self, message: str = "access denied") -> None:
        super().__init__(message, status_code=403, code="authorization_failed")


class RateLimitExceededError(GatewayError):
    def __init__(self, retry_after_seconds: int, message: str = "rate limit exceeded") -> None:
        super().__init__(
            message,
            status_code=429,
            code="rate_limit_exceeded",
            headers={"Retry-After": str(retry_after_seconds)},
        )


class QuotaExceededError(GatewayError):
    def __init__(self, message: str = "quota exceeded") -> None:
        super().__init__(message, status_code=429, code="quota_exceeded")


class RouteNotFoundError(GatewayError):
    def __init__(self, message: str = "route not found") -> None:
        super().__init__(message, status_code=404, code="route_not_found")


class BodyTooLargeError(GatewayError):
    def __init__(self, message: str = "request body too large") -> None:
        super().__init__(message, status_code=413, code="request_body_too_large")


class CircuitOpenError(GatewayError):
    def __init__(self, message: str = "upstream circuit is open") -> None:
        super().__init__(message, status_code=503, code="circuit_open")


class UpstreamTimeoutError(GatewayError):
    def __init__(self, message: str = "upstream timeout") -> None:
        super().__init__(message, status_code=504, code="upstream_timeout")


class UpstreamServiceError(GatewayError):
    def __init__(self, message: str = "upstream unavailable", *, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code, code="upstream_unavailable")


class AdminAuthenticationError(GatewayError):
    def __init__(self, message: str = "admin authentication failed") -> None:
        super().__init__(message, status_code=401, code="admin_authentication_failed")
