import logging
from collections.abc import Mapping, MutableMapping
from typing import Any, cast

import structlog
from structlog.types import Processor

from app.observability.correlation import request_id_var


def add_request_id(
    _logger: object, _method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """
    Processor that adds the current request ID from contextvars to the event dict.
    """
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def event_renamer(
    _logger: object, _method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """
    Ensures that the log message is always under the 'event' key.
    If 'msg' is provided, it renames it to 'event' if 'event' is missing or empty.
    """
    if "msg" in event_dict and ("event" not in event_dict or not event_dict["event"]):
        event_dict["event"] = event_dict.pop("msg")
    return event_dict


def configure_logging(level: str, json: bool) -> None:
    """
    Configures structlog with the specified log level and format.
    """
    processors: list[Processor] = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_request_id,
        event_renamer,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )

    log_level = int(getattr(logging, level.upper(), logging.INFO))

    structlog.configure(
        processors=[*processors, renderer],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Returns a structlog logger.
    """
    return cast(structlog.BoundLogger, structlog.get_logger(name))
