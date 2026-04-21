"""BaseTracerClient ABC.

Abstracts observability tracing (Langfuse v1, OpenTelemetry v2).
TracingError is non-critical — callers must not fail if tracing is down.
All methods may receive a None handle when tracing is disabled.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseTracerClient(ABC):

    @abstractmethod
    def start_trace(self, trace_id: str, name: str, metadata: dict | None = None) -> Any:
        """Start a new trace span. Return opaque handle for subsequent calls."""

    @abstractmethod
    def end_trace(self, handle: Any, output: str | None = None, token_usage: int | None = None) -> None:
        """End trace span with output data and token count."""

    @abstractmethod
    def log_error(self, handle: Any, error: Exception) -> None:
        """Attach error information to an active trace span."""
