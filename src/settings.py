from __future__ import annotations

from ipaddress import ip_network
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GATEWAY_",
        extra="ignore",
        env_file_encoding="utf-8",
    )

    env: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1

    request_timeout_ms: int = 30_000
    connect_timeout_ms: int = 5_000
    pool_timeout_ms: int = 5_000
    max_connections: int = 200
    max_keepalive_connections: int = 50
    global_concurrency_limit: int = 500
    max_request_body_bytes: int = 10 * 1024 * 1024

    metrics_enabled: bool = True
    tracing_enabled: bool = False
    enable_debug_http_logs: bool = False
    debug_http_log_max_request_body_bytes: int = 8 * 1024
    debug_http_log_max_response_body_bytes: int = 8 * 1024
    debug_http_log_max_stream_chunk_previews: int = 3

    admin_api_enabled: bool = False
    admin_api_token_hash: str | None = None
    admin_api_bind: str = "127.0.0.1"
    # NoDecode: the env value is a comma-separated list (see _split_allowlist), not JSON.
    admin_api_ip_allowlist: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["127.0.0.1/32"]
    )

    database_url: str
    redis_url: str

    upstream_base_url: str
    upstream_service_token: SecretStr
    upstream_service_token_header: str = "Authorization"
    upstream_stream_transport_mode: Literal["auto", "always", "never"] = "auto"
    upstream_signing_enabled: bool = True
    upstream_signing_key: SecretStr | None = None
    upstream_mtls_enabled: bool = False
    upstream_client_cert: Path | None = None
    upstream_client_key: Path | None = None
    upstream_ca_cert: Path | None = None

    config_dir: Path = Path("./config")
    route_config: Path = Path("./config/routes.yaml")
    policy_config: Path = Path("./config/policies.yaml")
    limit_config: Path = Path("./config/limits.yaml")
    logging_config: Path = Path("./config/logging.yaml")

    audit_retention_days: int = 30
    usage_retention_days: int = 90
    config_reload_interval_seconds: int = 30
    consumer_cache_ttl_seconds: int = 60
    enable_real_upstream_healthcheck: bool = False

    @field_validator("admin_api_ip_allowlist", mode="before")
    @classmethod
    def _split_allowlist(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("admin_api_ip_allowlist")
    @classmethod
    def _validate_allowlist(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for entry in value:
            normalized.append(str(ip_network(entry, strict=False)))
        return normalized

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        upper = value.upper()
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if upper not in valid:
            raise ValueError(f"unsupported log level {value!r}")
        return upper

    @model_validator(mode="after")
    def _validate_security(self) -> Self:
        if self.admin_api_enabled and not self.admin_api_token_hash:
            raise ValueError("admin_api_token_hash must be set when admin_api_enabled is true")
        if self.upstream_signing_enabled and self.upstream_signing_key is None:
            raise ValueError("upstream_signing_key must be configured when signing is enabled")
        if self.upstream_mtls_enabled:
            if not self.upstream_client_cert or not self.upstream_client_key:
                raise ValueError(
                    "upstream_client_cert and upstream_client_key are required when mTLS is enabled"
                )
        return self


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
