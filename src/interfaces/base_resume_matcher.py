"""BaseResumeMatcher ABC.

Abstracts the AI evaluation pipeline (CrewAI v1).
Service layer only knows this interface — never imports from crew/ directly.
"""

from abc import ABC, abstractmethod

from src.entities.evaluation_result import EvaluationResult


class BaseResumeMatcher(ABC):

    @abstractmethod
    async def evaluate(
        self,
        cv_text: str,
        jd_text: str,
        profile: str,
        flags: dict,
        token_budget: int,
    ) -> EvaluationResult:
        """Run multi-agent evaluation pipeline. Raises CrewExecutionError hierarchy."""
