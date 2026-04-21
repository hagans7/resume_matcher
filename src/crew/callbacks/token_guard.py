"""TokenGuard — Celery step_callback that monitors token usage during crew execution.

Registered as step_callback on the Crew object.
Called after each agent step completes.
Raises TokenBudgetExceededError if cumulative usage exceeds budget.
"""

from src.core.exceptions.app_exceptions import TokenBudgetExceededError
from src.core.logging.logger import get_logger

logger = get_logger(__name__)


class TokenGuard:

    def __init__(self, budget: int) -> None:
        self._budget = budget
        self._used = 0

    def check(self, step_output) -> None:
        """Called after each agent step. Raises TokenBudgetExceededError if over budget."""
        tokens = self._extract_tokens(step_output)
        self._used += tokens

        logger.debug(
            "token_guard_check",
            step_tokens=tokens,
            cumulative=self._used,
            budget=self._budget,
        )

        if self._used > self._budget:
            raise TokenBudgetExceededError(
                message=f"Token budget exceeded: used {self._used}, budget {self._budget}",
                used=self._used,
                budget=self._budget,
            )

    @property
    def total_used(self) -> int:
        return self._used

    @staticmethod
    def _extract_tokens(step_output) -> int:
        """Extract token count from CrewAI step output. Returns 0 if unavailable."""
        try:
            # CrewAI exposes token_usage on the step output object
            if hasattr(step_output, "token_usage"):
                usage = step_output.token_usage
                if hasattr(usage, "total_tokens"):
                    return int(usage.total_tokens)
            # Fallback: estimate from output text length (1 token ≈ 4 chars)
            if hasattr(step_output, "raw"):
                return max(1, len(str(step_output.raw)) // 4)
        except Exception:
            pass
        return 0
