"""Structured logging setup.

Two rendering modes:
- dev  → Rich console renderer with color and indentation (human-readable)
- prod → JSON renderer (machine-parseable, suitable for log aggregators)

Daily log rotation: logs/resume_matcher_YYYY-MM-DD.log

Usage:
    from src.core.logging.logger import get_logger
    logger = get_logger(__name__)
    logger.info("candidate_evaluated", candidate_id=cid, score=82, duration_ms=1540)
"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_log_level(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add log level string to event dict."""
    event_dict["level"] = method_name.upper()
    return event_dict


def _add_timestamp(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO-8601 timestamp to event dict."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def setup_logging(log_level: str = "DEBUG", log_format: str = "console") -> None:
    """Configure structlog. Call once at application startup.

    Args are sourced from settings — do not hardcode here.
    """
    # ── Shared processors (run regardless of renderer) ────────────────────────
    shared_processors: list = [
        _add_timestamp,
        _add_log_level,
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # ── Renderer selection ────────────────────────────────────────────────────
    if log_format == "console":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    # ── structlog configuration ───────────────────────────────────────────────
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.DEBUG)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── stdlib logging (for libraries that use logging.getLogger) ─────────────
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Daily rotating file handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / "resume_matcher.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(log_level.upper())

    # Suppress noisy library loggers in production
    for noisy in ("httpx", "httpcore", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound structlog logger for the given module name.

    Usage: self._logger = get_logger(__name__)
    """
    return structlog.get_logger(name)
