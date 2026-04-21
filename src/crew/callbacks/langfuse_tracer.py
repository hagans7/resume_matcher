"""CrewLangfuseTracer — task_callback that sends per-task trace data to Langfuse.

Registered as task_callback on the Crew object.
Called after each task completes.
Non-critical: all errors are caught and logged, never propagated.
"""

from typing import Any

from src.core.logging.logger import get_logger
from src.interfaces.base_tracer_client import BaseTracerClient

logger = get_logger(__name__)


class CrewLangfuseTracer:

    def __init__(self, tracer: BaseTracerClient, trace_id: str) -> None:
        self._tracer = tracer
        self._trace_id = trace_id
        self._handles: dict[str, Any] = {}

    def on_task_start(self, task_name: str, metadata: dict | None = None) -> None:
        """Start a Langfuse span for a task. Non-critical."""
        try:
            handle = self._tracer.start_trace(
                trace_id=f"{self._trace_id}:{task_name}",
                name=task_name,
                metadata=metadata or {},
            )
            self._handles[task_name] = handle
        except Exception as exc:
            logger.debug("langfuse_task_start_failed", task=task_name, error=str(exc))

    def on_task_complete(self, task_output) -> None:
        """End Langfuse span for completed task. Non-critical."""
        try:
            task_name = self._extract_task_name(task_output)
            handle = self._handles.get(task_name)
            if handle is None:
                return

            output_text = str(task_output.raw) if hasattr(task_output, "raw") else ""
            token_usage = self._extract_tokens(task_output)

            self._tracer.end_trace(
                handle=handle,
                output=output_text[:2000],  # truncate long outputs
                token_usage=token_usage,
            )
            logger.debug("langfuse_task_traced", task=task_name, tokens=token_usage)
        except Exception as exc:
            logger.debug("langfuse_task_complete_failed", error=str(exc))

    @staticmethod
    def _extract_task_name(task_output) -> str:
        """Extract task name from CrewAI task output object."""
        try:
            if hasattr(task_output, "task") and hasattr(task_output.task, "name"):
                return task_output.task.name
            if hasattr(task_output, "name"):
                return task_output.name
        except Exception:
            pass
        return "unknown_task"

    @staticmethod
    def _extract_tokens(task_output) -> int | None:
        """Extract token count from task output. Returns None if unavailable."""
        try:
            if hasattr(task_output, "token_usage"):
                usage = task_output.token_usage
                if hasattr(usage, "total_tokens"):
                    return int(usage.total_tokens)
        except Exception:
            pass
        return None
