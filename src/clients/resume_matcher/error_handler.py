"""ErrorHandler — normalizes CrewAI and LiteLLM exceptions to app exception hierarchy.

Service layer only knows AppBaseError hierarchy.
This module is the boundary where CrewAI-specific errors are translated.
"""

import asyncio

from src.core.exceptions.app_exceptions import (
    AgentExecutionError,
    CrewExecutionError,
    CrewTimeoutError,
    TokenBudgetExceededError,
)
from src.core.logging.logger import get_logger

logger = get_logger(__name__)


def normalize_crew_exception(exc: Exception, candidate_id: str) -> CrewExecutionError:
    """Map any exception from crew execution to a typed CrewExecutionError subclass.

    Args:
        exc: The caught exception
        candidate_id: For structured logging context

    Returns:
        A CrewExecutionError subclass — never re-raises the original.
    """
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    logger.error(
        "crew_execution_error",
        candidate_id=candidate_id,
        exc_type=exc_type,
        exc_msg=exc_msg[:500],
    )

    # Already a typed app exception — pass through
    if isinstance(exc, TokenBudgetExceededError):
        return exc

    if isinstance(exc, asyncio.TimeoutError):
        return CrewTimeoutError(
            f"Crew execution timed out for candidate {candidate_id}",
            detail={"candidate_id": candidate_id},
        )

    # LiteLLM / OpenAI rate limit errors
    if any(kw in exc_msg.lower() for kw in ("rate limit", "429", "too many requests")):
        return AgentExecutionError(
            message=f"LLM rate limit exceeded: {exc_msg[:200]}",
            agent_name="unknown",
            detail={"candidate_id": candidate_id, "exc_type": exc_type},
        )

    # LiteLLM authentication errors
    if any(kw in exc_msg.lower() for kw in ("401", "unauthorized", "invalid api key", "authentication")):
        return AgentExecutionError(
            message=f"LLM authentication failed: {exc_msg[:200]}",
            agent_name="unknown",
            detail={"candidate_id": candidate_id},
        )

    # CrewAI agent-specific errors
    if "agent" in exc_msg.lower() or exc_type in ("TaskError", "AgentError"):
        return AgentExecutionError(
            message=f"Agent execution failed: {exc_msg[:300]}",
            agent_name=_extract_agent_name(exc_msg),
            detail={"candidate_id": candidate_id, "exc_type": exc_type},
        )

    # Generic fallback
    return CrewExecutionError(
        message=f"Crew execution failed: {exc_msg[:300]}",
        detail={"candidate_id": candidate_id, "exc_type": exc_type},
    )


def _extract_agent_name(error_msg: str) -> str:
    """Attempt to extract agent name from error message. Returns 'unknown' if not found."""
    known_agents = [
        "resume_profiler", "jd_analyst", "skill_matcher",
        "experience_evaluator", "education_assessor", "red_flag_detector",
        "soft_skill_analyzer", "project_scorer", "score_aggregator", "report_writer",
    ]
    msg_lower = error_msg.lower()
    for agent in known_agents:
        if agent.replace("_", " ") in msg_lower or agent in msg_lower:
            return agent
    return "unknown"
