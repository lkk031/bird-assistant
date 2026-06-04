"""Structured logging configuration using structlog."""

import logging
import sys

import structlog

from assistant_bird.config import get_settings


def setup_logging() -> None:
    """Configure structlog for the application."""
    settings = get_settings()

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
            if sys.stderr.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger for the given module name."""
    return structlog.get_logger(name)  # type: ignore[return-value]
