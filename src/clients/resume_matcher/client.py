"""CrewAIResumeMatcherClient — implements BaseResumeMatcher using CrewAI.

This is the only file that orchestrates the crew execution end-to-end:
  1. Build crew via builder (factories handle agent/task assembly)
  2. Execute crew.kickoff() with inputs
  3. Parse output via output_parser
  4. Normalize errors via error_handler
  5. Return EvaluationResult entity

Service layer never imports from crew/ — only imports this client via BaseResumeMatcher.
Token budget monitoring is handled by TokenGuard callback inside the crew.
"""

import asyncio
import time

from src.core.exceptions.app_exceptions import (
    CrewExecutionError,
    TokenBudgetExceededError,
)
from src.core.logging.logger import get_logger
from src.crew import builder
from src.crew.version import CREW_VERSION
from src.clients.resume_matcher.error_handler import normalize_crew_exception
from src.clients.resume_matcher.output_parser import parse_crew_output
from src.entities.evaluation_result import EvaluationResult
from src.interfaces.base_resume_matcher import BaseResumeMatcher
from src.interfaces.base_tracer_client import BaseTracerClient

logger = get_logger(__name__)


class CrewAIResumeMatcherClient(BaseResumeMatcher):
    """Executes CrewAI multi-agent evaluation pipeline.

    Import rule: only providers/infrastructure.py and tests may instantiate this.
    Service layer uses BaseResumeMatcher interface only.
    """

    def __init__(
        self,
        llm_model: str,
        llm_api_key: str,
        llm_base_url: str | None,
        llm_max_rpm: int,
        llm_verbose: bool,
        crew_execution_timeout: int,
        tracer: BaseTracerClient,
    ) -> None:
        self._llm_model = llm_model
        self._llm_api_key = llm_api_key
        self._llm_base_url = llm_base_url
        self._llm_max_rpm = llm_max_rpm
        self._llm_verbose = llm_verbose
        self._timeout = crew_execution_timeout
        self._tracer = tracer

        logger.info(
            "crew_matcher_initialized",
            model=llm_model,
            base_url=llm_base_url or "openai_direct",
            timeout=crew_execution_timeout,
        )

    async def evaluate(
        self,
        cv_text: str,
        jd_text: str,
        profile: str,
        flags: dict,
        token_budget: int,
        candidate_id: str = "unknown",
    ) -> EvaluationResult:
        """Run full multi-agent evaluation pipeline. Raises CrewExecutionError hierarchy.

        Args:
            cv_text: Masked, extracted CV text (from PrepareCVTextService)
            jd_text: Raw job description text
            profile: EVALUATION_MODE_QUICK | STANDARD | FULL
            flags: {'include_soft_skill': bool, 'include_project_scorer': bool}
            token_budget: Max tokens for this run (from settings per profile)
            candidate_id: For logging and tracing context
        """
        start_ms = int(time.time() * 1000)

        trace_handle = self._tracer.start_trace(
            trace_id=candidate_id,
            name=f"crew_evaluation_{profile}",
            metadata={
                "profile": profile,
                "flags": flags,
                "token_budget": token_budget,
                "crew_version": CREW_VERSION,
                "llm_model": self._llm_model,
            },
        )

        try:
            # Build crew — factories handle agent/task selection
            crew, token_guard = builder.build_crew(
                profile=profile,
                flags=flags,
                llm_model=self._llm_model,
                llm_api_key=self._llm_api_key,
                llm_base_url=self._llm_base_url,
                llm_max_rpm=self._llm_max_rpm,
                llm_verbose=self._llm_verbose,
                token_budget=token_budget,
                tracer=self._tracer,
                trace_id=candidate_id,
                inputs={"cv_text": cv_text, "jd_text": jd_text},
            )

            logger.info(
                "crew_kickoff_starting",
                candidate_id=candidate_id,
                profile=profile,
                token_budget=token_budget,
            )

            # Execute crew synchronously in thread executor
            # (CrewAI kickoff is synchronous; we wrap to avoid blocking the event loop)
            loop = asyncio.get_event_loop()
            crew_output = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: crew.kickoff(inputs={"cv_text": cv_text, "jd_text": jd_text}),
                ),
                timeout=self._timeout,
            )

            processing_ms = int(time.time() * 1000) - start_ms
            token_used = token_guard.total_used

            logger.info(
                "crew_kickoff_complete",
                candidate_id=candidate_id,
                processing_ms=processing_ms,
                token_used=token_used,
            )

            # Parse CrewAI output → EvaluationResult entity
            result = parse_crew_output(
                crew_output=crew_output,
                token_used=token_used,
                processing_ms=processing_ms,
                crew_version=CREW_VERSION,
                llm_model=self._llm_model,
            )

            self._tracer.end_trace(
                handle=trace_handle,
                output=f"score={result.overall_score} verdict={result.verdict}",
                token_usage=token_used,
            )

            return result

        except asyncio.TimeoutError as exc:
            processing_ms = int(time.time() * 1000) - start_ms
            self._tracer.log_error(trace_handle, exc)
            app_exc = normalize_crew_exception(exc, candidate_id)
            logger.error(
                "crew_timeout",
                candidate_id=candidate_id,
                timeout_seconds=self._timeout,
                processing_ms=processing_ms,
            )
            raise app_exc from exc

        except TokenBudgetExceededError:
            # Pass through — already typed, service layer handles partial result
            self._tracer.log_error(trace_handle, TokenBudgetExceededError)
            raise

        except CrewExecutionError:
            # Already normalized upstream (e.g. from token_guard) — pass through
            raise

        except Exception as exc:
            processing_ms = int(time.time() * 1000) - start_ms
            self._tracer.log_error(trace_handle, exc)
            app_exc = normalize_crew_exception(exc, candidate_id)
            logger.error(
                "crew_unexpected_error",
                candidate_id=candidate_id,
                processing_ms=processing_ms,
                exc_type=type(exc).__name__,
            )
            raise app_exc from exc
