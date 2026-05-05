"""Logging configuration for PyServiceLab.

Provides ``setup_logging`` for one-time initialisation and
``get_logger`` / ``StructuredLogger`` / ``ServiceLogger`` for per-module use.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Configure application-wide logging.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to write logs to in addition to stdout.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=numeric_level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a standard library logger by name."""
    return logging.getLogger(name)


class StructuredLogger:
    """Thin wrapper around :class:`logging.Logger` that appends key=value context.

    Example::

        log = StructuredLogger("mymodule", {"request_id": "abc123"})
        log.info("User created", user_id=42)
        # → 2024-01-01 [INFO] mymodule: User created | request_id=abc123 user_id=42
    """

    def __init__(self, name: str, context: Optional[dict] = None) -> None:
        self._logger = get_logger(name)
        self._context: dict = context or {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def with_context(self, **kwargs: object) -> "StructuredLogger":
        """Return a new logger with additional context merged in."""
        return StructuredLogger(self._logger.name, {**self._context, **kwargs})

    def info(self, message: str, **kwargs: object) -> None:
        """Log at INFO level."""
        self._logger.info(self._format(message, kwargs))

    def warning(self, message: str, **kwargs: object) -> None:
        """Log at WARNING level."""
        self._logger.warning(self._format(message, kwargs))

    def error(self, message: str, **kwargs: object) -> None:
        """Log at ERROR level."""
        self._logger.error(self._format(message, kwargs))

    def debug(self, message: str, **kwargs: object) -> None:
        """Log at DEBUG level."""
        self._logger.debug(self._format(message, kwargs))

    def critical(self, message: str, **kwargs: object) -> None:
        """Log at CRITICAL level."""
        self._logger.critical(self._format(message, kwargs))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _format(self, message: str, extra: dict) -> str:
        ctx = {**self._context, **extra}
        if not ctx:
            return message
        pairs = " ".join(f"{k}={v}" for k, v in ctx.items())
        return f"{message} | {pairs}"


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Each record always contains ``timestamp``, ``level``, ``logger``, and
    ``message``.  When a record carries the extra fields set by
    :class:`ServiceLogger` (``operation``, ``entity_id``, ``user_id``), they
    are included verbatim; ``None`` values are omitted so the output stays
    compact.

    Example output::

        {"timestamp": "2024-01-15T10:30:00Z", "level": "INFO",
         "logger": "pyservicelab.services.user_service",
         "message": "User 'alice' created",
         "operation": "user.create_user", "entity_id": 1}
    """

    _EXTRA_FIELDS = ("operation", "entity_id", "user_id")

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                data[field] = value
        return json.dumps(data)


class ServiceLogger:
    """Logger that emits structured records for service operations.

    Each call to :meth:`log_operation` attaches ``operation``,
    ``entity_id``, and ``user_id`` as extra fields on the
    :class:`logging.LogRecord`, making them available to any attached
    handler or formatter (including :class:`JsonFormatter`).

    Example::

        _log = ServiceLogger(__name__)
        _log.log_operation(
            "User 'alice' created",
            operation="user.create_user",
            entity_id=1,
            user_id=None,
        )
    """

    def __init__(self, name: str) -> None:
        self._logger = get_logger(name)

    def log_operation(
        self,
        message: str,
        *,
        operation: str,
        entity_id: Optional[int] = None,
        user_id: Optional[int] = None,
        level: str = "info",
    ) -> None:
        """Emit a structured log record for a service operation.

        Args:
            message: Human-readable description of what happened.
            operation: Dot-namespaced operation name, e.g. ``"user.create_user"``.
            entity_id: Primary key of the entity that was acted upon.
            user_id: ID of the user who performed the action (None for system ops).
            level: Logging level name (default: ``"info"``).
        """
        extra: dict[str, object] = {
            "operation": operation,
            "entity_id": entity_id,
            "user_id": user_id,
        }
        getattr(self._logger, level)(message, extra=extra)


class CapturingHandler(logging.Handler):
    """A :class:`logging.Handler` that stores emitted records in a list.

    Designed for use in tests to assert that specific log records were
    produced without relying on stdout or log files::

        handler = CapturingHandler()
        logging.getLogger("pyservicelab.services.user_service").addHandler(handler)

        user_service.create_user(...)

        assert any(
            getattr(r, "operation", None) == "user.create_user"
            for r in handler.records
        )
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def clear(self) -> None:
        """Remove all captured records."""
        self.records.clear()
