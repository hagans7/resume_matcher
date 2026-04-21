"""LangfuseTracerClient — Langfuse implementation of BaseTracerClient.

TracingError is non-critical: all methods are wrapped in try/except.
If Langfuse is down or keys are missing, app continues without tracing.

When langfuse_enabled=False (no keys), all methods return immediately
with a sentinel NullHandle — no external calls are made.
"""

from typing import Any

from src.core.exceptions.app_exceptions import TracingError
from src.core.logging.logger import get_logger
from src.interfaces.base_tracer_client import BaseTracerClient

logger = get_logger(__name__)


class _NullHandle:
    """Sentinel returned when tracing is disabled. All operations on it are no-ops."""
    pass


class LangfuseTracerClient(BaseTracerClient):

    def __init__(
        self,
        public_key: str | None,
        secret_key: str | None,
        host: str,
    ) -> None:
        self._enabled = bool(public_key and secret_key)
        self._client = None

        if self._enabled:
            try:
                from langfuse import Langfuse
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
                logger.info("langfuse_tracer_initialized", host=host)
            except Exception as exc:
                # Non-critical: disable tracing if Langfuse init fails
                logger.warning("langfuse_init_failed", error=str(exc))
                self._enabled = False
        else:
            logger.info("langfuse_tracing_disabled", reason="keys not configured")

    def start_trace(
        self,
        trace_id: str,
        name: str,
        metadata: dict | None = None,
    ) -> Any:
        """Start a trace span. Returns handle or NullHandle if disabled."""
        if not self._enabled or self._client is None:
            return _NullHandle()
        try:
            trace = self._client.trace(
                id=trace_id,
                name=name,
                metadata=metadata or {},
            )
            span = trace.span(name=name)
            logger.debug("trace_started", trace_id=trace_id, name=name)
            return span
        except Exception as exc:
            logger.warning("trace_start_failed", trace_id=trace_id, error=str(exc))
            return _NullHandle()

    def end_trace(
        self,
        handle: Any,
        output: str | None = None,
        token_usage: int | None = None,
    ) -> None:
        """End trace span with output. No-op on NullHandle."""
        if isinstance(handle, _NullHandle) or not self._enabled:
            return
        try:
            handle.end(
                output=output,
                usage={"total_tokens": token_usage} if token_usage else None,
            )
            self._client.flush()
        except Exception as exc:
            logger.warning("trace_end_failed", error=str(exc))

    def log_error(self, handle: Any, error: Exception) -> None:
        """Attach error to active trace span. No-op on NullHandle."""
        if isinstance(handle, _NullHandle) or not self._enabled:
            return
        try:
            handle.end(
                output=str(error),
                level="ERROR",
                status_message=type(error).__name__,
            )
            self._client.flush()
        except Exception as exc:
            logger.warning("trace_error_log_failed", error=str(exc))
