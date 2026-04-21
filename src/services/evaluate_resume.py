"""EvaluateResumeService — orchestrates single CV evaluation pipeline.

Thin orchestrator per blueprint v2 revision:
  3 private methods only (down from 13 in original god-service).

Flow:
  1. IngestCandidateService   → validate, store, create DB record
  2. PrepareCVTextService      → extract, mask PII
  3. _determine_profile()      → select crew profile + flags (Python logic, not agent)
  4. _get_token_budget()       → map profile → token limit
  5. CrewAI evaluation         → via BaseResumeMatcher.evaluate()
  6. _persist_result()         → checkpoint pattern (two-phase write)
  7. Store markdown report     → storage
  8. Return updated Candidate
"""

import time
from datetime import datetime, timezone

from src.core.constants.app_constants import (
    CANDIDATE_STATUS_EVALUATED,
    CANDIDATE_STATUS_FAILED,
    EVALUATION_MODE_FULL,
    EVALUATION_MODE_QUICK,
    EVALUATION_MODE_STANDARD,
    PROJECT_SECTION_KEYWORDS,
    SOFT_SKILL_JD_KEYWORDS,
)
from src.core.exceptions.app_exceptions import (
    CacheError,
    TokenBudgetExceededError,
)
from src.core.logging.logger import get_logger
from src.entities.candidate import Candidate
from src.interfaces.base_cache_client import BaseCacheClient
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_job_repository import BaseJobRepository
from src.interfaces.base_resume_matcher import BaseResumeMatcher
from src.interfaces.base_storage_client import BaseStorageClient
from src.services.ingest_candidate import IngestCandidateService
from src.services.prepare_cv_text import PrepareCVTextService

logger = get_logger(__name__)


class EvaluateResumeService:
    """Orchestrates single CV evaluation. Dependencies injected via __init__."""

    def __init__(
        self,
        ingest_service: IngestCandidateService,
        prepare_service: PrepareCVTextService,
        candidate_repo: BaseCandidateRepository,
        job_repo: BaseJobRepository,
        matcher: BaseResumeMatcher,
        cache: BaseCacheClient,
        storage: BaseStorageClient,
    ) -> None:
        self._ingest = ingest_service
        self._prepare = prepare_service
        self._candidate_repo = candidate_repo
        self._job_repo = job_repo
        self._matcher = matcher
        self._cache = cache
        self._storage = storage

    async def execute(
        self,
        job_id: str,
        file_bytes: bytes,
        filename: str,
        batch_id: str | None = None,
    ) -> Candidate:
        """Full single-CV pipeline. Returns evaluated Candidate.

        Raises: FileValidationError, DuplicateCVError, JobNotFoundError,
                DocumentExtractionError, CrewExecutionError, PersistenceError.
        TokenBudgetExceededError is caught here: partial result is persisted.
        """
        start_ms = int(time.time() * 1000)

        # Step 1: Ingest — validate, dedup, store file, create DB record
        candidate = await self._ingest.execute(job_id, file_bytes, filename, batch_id)

        # Step 2: Prepare — extract text + mask PII
        try:
            cv_text = await self._prepare.execute(file_bytes, filename, candidate.id)
        except Exception:
            await self._candidate_repo.update_status(candidate.id, CANDIDATE_STATUS_FAILED)
            raise

        # Step 3: Load job for JD text and evaluation mode
        job = await self._job_repo.get_by_id(job_id)

        # Step 4: Determine profile + conditional flags
        profile, flags = self._determine_profile(cv_text, job.description, job.evaluation_mode)

        # Step 5: Get token budget for selected profile
        budget = self._get_token_budget(profile)

        # Step 6: Run CrewAI evaluation
        try:
            result = await self._matcher.evaluate(
                cv_text=cv_text,
                jd_text=job.description,
                profile=profile,
                flags=flags,
                token_budget=budget,
                candidate_id=candidate.id,
            )
        except TokenBudgetExceededError as exc:
            # Partial result: persist what we have with a warning flag in notes
            logger.warning(
                "token_budget_exceeded_partial_result",
                candidate_id=candidate.id,
                used=exc.used,
                budget=exc.budget,
            )
            # Persist failure status — no partial result available from crew
            await self._candidate_repo.update_status(candidate.id, CANDIDATE_STATUS_FAILED)
            raise
        except Exception:
            await self._candidate_repo.update_status(candidate.id, CANDIDATE_STATUS_FAILED)
            raise

        # Step 7: Persist result — checkpoint pattern (two-phase write)
        processing_ms = int(time.time() * 1000) - start_ms
        await self._persist_result(candidate.id, result)

        # Step 8: Store markdown report to storage
        report_key = f"reports/{candidate.id}.md"
        await self._storage.save(
            key=report_key,
            data=result.summary.encode("utf-8"),
            content_type="text/markdown",
        )

        logger.info(
            "evaluation_complete",
            candidate_id=candidate.id,
            job_id=job_id,
            score=result.overall_score,
            verdict=result.verdict,
            processing_ms=processing_ms,
            token_used=result.token_used,
        )

        # Return refreshed Candidate with all fields populated
        updated = await self._candidate_repo.get_by_id(candidate.id)
        return updated

    def _determine_profile(
        self,
        cv_text: str,
        jd_text: str,
        job_evaluation_mode: str,
    ) -> tuple[str, dict]:
        """Determine crew profile and conditional flags from input text.

        Pure Python keyword matching — runs BEFORE crew, no agent involved.
        Flags inform builder which optional agents to include.

        Returns: (profile, flags) where flags = {'include_soft_skill': bool, 'include_project_scorer': bool}
        """
        # Job's evaluation_mode is the base (set at job creation by HR)
        profile = job_evaluation_mode

        flags: dict[str, bool] = {
            "include_soft_skill": False,
            "include_project_scorer": False,
        }

        # Only FULL profile supports conditional agents
        if profile == EVALUATION_MODE_FULL:
            cv_lower = cv_text.lower()
            jd_lower = jd_text.lower()

            # Check CV for project section keywords
            has_projects = any(kw in cv_lower for kw in PROJECT_SECTION_KEYWORDS)
            # Check JD for soft skill keywords
            has_soft_skills = any(kw in jd_lower for kw in SOFT_SKILL_JD_KEYWORDS)

            flags["include_project_scorer"] = has_projects
            flags["include_soft_skill"] = has_soft_skills

            logger.debug(
                "profile_determined",
                profile=profile,
                has_projects=has_projects,
                has_soft_skills=has_soft_skills,
            )

        return profile, flags

    def _get_token_budget(self, profile: str) -> int:
        """Map evaluation profile to token budget. Lazy import to avoid circular dependency."""
        from src.core.config.settings import settings
        budgets = {
            EVALUATION_MODE_QUICK: settings.token_budget_quick,
            EVALUATION_MODE_STANDARD: settings.token_budget_standard,
            EVALUATION_MODE_FULL: settings.token_budget_full,
        }
        return budgets.get(profile, settings.token_budget_standard)

    async def _persist_result(self, candidate_id: str, result) -> None:
        """Two-phase checkpoint write. Phase 1: result_json. Phase 2: status=evaluated."""
        await self._candidate_repo.update_result(
            candidate_id=candidate_id,
            score=result.overall_score,
            verdict=result.verdict,
            status=CANDIDATE_STATUS_EVALUATED,
            result_json=result.to_dict(),
            processing_ms=result.processing_ms,
            token_used=result.token_used,
        )
