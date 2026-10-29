from __future__ import annotations

import logging
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, cast

import structlog
import yaml

from src.security.redaction import DEFAULT_REDACTED_KEYS, redact_mapping


def _redaction_processor(
    _: Any,
    __: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    keys = event_dict.pop("_redacted_keys_override", DEFAULT_REDACTED_KEYS)
    return redact_mapping(dict(event_dict), keys=set(keys))


def load_logging_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {"service_name": "openlimits-vps-gateway", "renderer": "console"}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data


def configure_logging(log_level: str, config_path: Path) -> None:
    logging_config = load_logging_config(config_path)
    renderer_name = logging_config.get("renderer", "console")
    redacted_keys = logging_config.get("redacted_keys", sorted(DEFAULT_REDACTED_KEYS))

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    renderer: structlog.types.Processor
    if renderer_name == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()
    processors: list[Any] = [
        lambda _, __, event_dict: {
            **event_dict,
            "_redacted_keys_override": redacted_keys,
        },
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        _redaction_processor,
        renderer,
    ]
    wrapper_class = structlog.make_filtering_bound_logger(getattr(logging, log_level, logging.INFO))

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(message)s",
    )
    structlog.configure(
        processors=processors,
        wrapper_class=wrapper_class,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
