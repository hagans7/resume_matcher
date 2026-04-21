"""Unit tests for ErrorHandler — verifies LLM exception normalization.

Bug guard: LiteLLM/OpenRouter errors must be translated to typed AppBaseError
subclasses so that:
  1. RateLimitError (429) → AgentExecutionError → Celery can retry
  2. AuthError (401) → AgentExecutionError → surface as 503 cleanly
  3. Generic errors → CrewExecutionError → not silently swallowed
"""

import pytest

from src.clients.resume_matcher.error_handler import normalize_crew_exception
from src.core.exceptions.app_exceptions import (
    AgentExecutionError,
    CrewExecutionError,
    CrewTimeoutError,
    TokenBudgetExceededError,
)


CANDIDATE_ID = "cand-test-123"


class TestRateLimitNormalization:
    """429 / rate limit errors must become AgentExecutionError for Celery retry."""

    def test_litellm_rate_limit_error(self):
        exc = Exception(
            "litellm.RateLimitError: RateLimitError: OpenrouterException - "
            '{"error":{"code":429}}'
        )
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, AgentExecutionError)
        assert "LLM rate limit exceeded" in result.message

    def test_429_in_message(self):
        exc = Exception("Provider returned error code 429 Too Many Requests")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, AgentExecutionError)
        assert "LLM rate limit exceeded" in result.message

    def test_too_many_requests_phrase(self):
        exc = Exception("too many requests from this IP, please retry")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, AgentExecutionError)
        assert "LLM rate limit exceeded" in result.message

    def test_rate_limit_result_has_candidate_id_in_detail(self):
        exc = Exception("rate limit exceeded")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert result.detail.get("candidate_id") == CANDIDATE_ID


class TestAuthErrorNormalization:
    """401 / unauthorized errors must become AgentExecutionError."""

    def test_401_in_message(self):
        exc = Exception("401 Unauthorized: Invalid API key")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, AgentExecutionError)
        assert "LLM authentication failed" in result.message

    def test_invalid_api_key_phrase(self):
        exc = Exception("invalid api key provided for this endpoint")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, AgentExecutionError)
        assert "LLM authentication failed" in result.message

    def test_unauthorized_phrase(self):
        exc = Exception("unauthorized: token expired")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, AgentExecutionError)
        assert "LLM authentication failed" in result.message


class TestTimeoutNormalization:
    """asyncio.TimeoutError must become CrewTimeoutError."""

    def test_asyncio_timeout(self):
        import asyncio
        exc = asyncio.TimeoutError()
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, CrewTimeoutError)
        assert CANDIDATE_ID in result.message

    def test_timeout_result_has_candidate_id(self):
        import asyncio
        exc = asyncio.TimeoutError()
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert result.detail.get("candidate_id") == CANDIDATE_ID


class TestTokenBudgetPassthrough:
    """TokenBudgetExceededError must be returned as-is (not wrapped)."""

    def test_token_budget_passes_through(self):
        exc = TokenBudgetExceededError("Token budget exceeded", used=5000, budget=4000, detail={})
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert result is exc  # same object, not wrapped


class TestGenericFallback:
    """Unknown exceptions fall back to CrewExecutionError."""

    def test_generic_exception_becomes_crew_execution_error(self):
        exc = Exception("Some unexpected error from crewai internals")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        assert isinstance(result, CrewExecutionError)
        assert "Crew execution failed" in result.message

    def test_bad_request_400_fallback(self):
        """400 BadRequest (wrong model name etc.) → generic CrewExecutionError.

        This is acceptable — bad requests indicate config error, not transient failure.
        Celery should not retry config errors.
        """
        exc = Exception("litellm.BadRequestError: qwen3-6b is not valid model ID code 400")
        result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
        # Either CrewExecutionError or AgentExecutionError is acceptable
        assert isinstance(result, CrewExecutionError)
        assert CANDIDATE_ID in str(result.detail)

    def test_result_always_a_crew_execution_error_subclass(self):
        """normalize_crew_exception must NEVER return None or re-raise."""
        for exc in [
            Exception("random error"),
            ValueError("value issue"),
            RuntimeError("runtime issue"),
            Exception(""),
        ]:
            result = normalize_crew_exception(exc, candidate_id=CANDIDATE_ID)
            assert isinstance(result, CrewExecutionError), (
                f"Expected CrewExecutionError for {exc!r}, got {type(result)}"
            )