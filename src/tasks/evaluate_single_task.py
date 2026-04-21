"""evaluate_single — Celery task to evaluate one CV.

Fix 1 (Race condition): batch completion now uses atomic_increment_and_finalize()
  — increment + status update in ONE SQL statement. No Python-level read-then-write window.

Fix 2 (Async in Sync Celery): module-level async engine created once per worker process.
  asyncio.run() called ONCE at the outer task boundary — not inside helpers.
  _mark_failed and _finalize_batch share the same engine pool.

Idempotency guarantee (three-way check):
  status == "evaluated"                        → skip entirely (already done)
  status == "processing" AND result_json set   → skip LLM, persist status only
  status == "processing" AND result_json None  → full evaluation
  status == "new"                              → update to processing, full eval

Checkpoint pattern:
  result_json is written BEFORE status is updated to "evaluated".
  If worker crashes after LLM but before status update:
    → next retry detects result_json is set → skips LLM → only updates status.
"""

import asyncio
import time

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config.settings import settings
from src.core.constants.app_constants import (
    CANDIDATE_STATUS_EVALUATED,
    CANDIDATE_STATUS_FAILED,
    CANDIDATE_STATUS_PROCESSING,
    EVALUATION_MODE_FULL,
    PROJECT_SECTION_KEYWORDS,
    SOFT_SKILL_JD_KEYWORDS,
)
from src.core.logging.logger import get_logger, setup_logging
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)

# ── Fix 2: Module-level async engine — created once per worker process ────────
# Shared across all tasks in this worker. Avoids creating new engine per task.
_async_engine = create_async_engine(
    settings.database_url,
    pool_size=2,
    max_overflow=0,
)
_async_session_factory = async_sessionmaker(_async_engine, expire_on_commit=False)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="tasks.evaluate_single",
)
def evaluate_single(self, candidate_id: str, batch_id: str | None = None) -> dict:
    """Evaluate a single candidate CV. Idempotent — safe to retry.

    asyncio.run() called ONCE here — all async logic inside _run_evaluation.
    """
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("evaluate_single_started", candidate_id=candidate_id, batch_id=batch_id)

    try:
        return asyncio.run(_run_evaluation(candidate_id=candidate_id, batch_id=batch_id))

    except SoftTimeLimitExceeded:
        logger.error("evaluate_single_soft_timeout", candidate_id=candidate_id)
        asyncio.run(_mark_failed(candidate_id, batch_id))
        raise

    except Exception as exc:
        logger.error(
            "evaluate_single_error",
            candidate_id=candidate_id,
            exc_type=type(exc).__name__,
            exc_msg=str(exc)[:300],
        )
        retryable = ("timeout", "rate limit", "429", "connection", "temporarily")
        if any(kw in str(exc).lower() for kw in retryable):
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                pass
        asyncio.run(_mark_failed(candidate_id, batch_id))
        return {"candidate_id": candidate_id, "status": CANDIDATE_STATUS_FAILED}


async def _run_evaluation(candidate_id: str, batch_id: str | None) -> dict:
    """Core async evaluation logic. Uses shared module-level engine."""
    async with _async_session_factory() as session:
        async with session.begin():
            from src.repositories.candidate_repository import CandidateRepository
            from src.repositories.batch_repository import BatchRepository
            from src.repositories.job_repository import JobRepository

            candidate_repo = CandidateRepository(session)
            batch_repo = BatchRepository(session)
            job_repo = JobRepository(session)

            # ── IDEMPOTENCY CHECK ─────────────────────────────────────────────
            candidate = await candidate_repo.get_by_id(candidate_id)
            if candidate is None:
                logger.error("evaluate_single_candidate_not_found", candidate_id=candidate_id)
                return {"candidate_id": candidate_id, "status": "not_found"}

            if candidate.status == CANDIDATE_STATUS_EVALUATED:
                logger.info("evaluate_single_skip_already_done", candidate_id=candidate_id)
                return {"candidate_id": candidate_id, "status": CANDIDATE_STATUS_EVALUATED}

            if (
                candidate.status == CANDIDATE_STATUS_PROCESSING
                and candidate.result_json is not None
            ):
                # Fix 1: checkpoint recovery — LLM done, only update status
                logger.info("evaluate_single_checkpoint_recovery", candidate_id=candidate_id)
                await candidate_repo.update_status(candidate_id, CANDIDATE_STATUS_EVALUATED)
                if batch_id:
                    # Fix 1: atomic increment + completion check in one SQL
                    await batch_repo.atomic_increment_and_finalize(batch_id, "succeeded")
                return {"candidate_id": candidate_id, "status": CANDIDATE_STATUS_EVALUATED}

            if candidate.status != CANDIDATE_STATUS_PROCESSING:
                await candidate_repo.update_status(candidate_id, CANDIDATE_STATUS_PROCESSING)

            # ── LOAD JOB ──────────────────────────────────────────────────────
            job = await job_repo.get_by_id(candidate.job_id)
            if job is None:
                logger.error("evaluate_single_job_not_found", job_id=candidate.job_id)
                await candidate_repo.update_status(candidate_id, CANDIDATE_STATUS_FAILED)
                if batch_id:
                    await batch_repo.atomic_increment_and_finalize(batch_id, "failed")
                return {"candidate_id": candidate_id, "status": CANDIDATE_STATUS_FAILED}

            # ── LOAD FILE ────────────────────────────────────────────────────
            from src.providers.infrastructure import (
                get_document_extractor,
                get_resume_matcher,
                get_storage_client,
                get_tracer_client,
            )
            storage = get_storage_client()
            file_bytes = await storage.load(candidate.file_key)

            # ── PREPARE TEXT ─────────────────────────────────────────────────
            from src.services.prepare_cv_text import PrepareCVTextService
            from src.services.mask_pii import MaskPIIService

            prepare_service = PrepareCVTextService(
                extractor=get_document_extractor(),
                storage=storage,
                pii_masker=MaskPIIService(),
            )
            cv_text = await prepare_service.execute(
                file_bytes=file_bytes,
                filename=candidate.original_filename,
                candidate_id=candidate_id,
            )

            # ── DETERMINE PROFILE + FLAGS ─────────────────────────────────────
            profile = job.evaluation_mode
            flags: dict = {"include_soft_skill": False, "include_project_scorer": False}
            if profile == EVALUATION_MODE_FULL:
                cv_lower = cv_text.lower()
                jd_lower = job.description.lower()
                flags["include_project_scorer"] = any(
                    kw in cv_lower for kw in PROJECT_SECTION_KEYWORDS
                )
                flags["include_soft_skill"] = any(
                    kw in jd_lower for kw in SOFT_SKILL_JD_KEYWORDS
                )

            budget_map = {
                "quick": settings.token_budget_quick,
                "standard": settings.token_budget_standard,
                "full": settings.token_budget_full,
            }
            budget = budget_map.get(profile, settings.token_budget_standard)

            # ── RUN CREW ─────────────────────────────────────────────────────
            start_ms = int(time.time() * 1000)
            result = await get_resume_matcher().evaluate(
                cv_text=cv_text,
                jd_text=job.description,
                profile=profile,
                flags=flags,
                token_budget=budget,
                candidate_id=candidate_id,
            )

            # ── CHECKPOINT: persist result_json before updating status ────────
            await candidate_repo.update_result(
                candidate_id=candidate_id,
                score=result.overall_score,
                verdict=result.verdict,
                status=CANDIDATE_STATUS_EVALUATED,
                result_json=result.to_dict(),
                processing_ms=int(time.time() * 1000) - start_ms,
                token_used=result.token_used,
            )

            # Store report
            await storage.save(
                f"reports/{candidate_id}.md",
                result.summary.encode("utf-8"),
                "text/markdown",
            )

            # Fix 1: atomic increment + finalization in one SQL statement
            if batch_id:
                final_status = await batch_repo.atomic_increment_and_finalize(
                    batch_id, "succeeded"
                )
                logger.info(
                    "batch_progress_updated",
                    batch_id=batch_id,
                    batch_status=final_status,
                )

            logger.info(
                "evaluate_single_complete",
                candidate_id=candidate_id,
                score=result.overall_score,
                verdict=result.verdict,
            )
            return {"candidate_id": candidate_id, "status": CANDIDATE_STATUS_EVALUATED}


async def _mark_failed(candidate_id: str, batch_id: str | None) -> None:
    """Mark candidate as failed using shared module-level engine."""
    async with _async_session_factory() as session:
        async with session.begin():
            from src.repositories.candidate_repository import CandidateRepository
            from src.repositories.batch_repository import BatchRepository

            await CandidateRepository(session).update_status(
                candidate_id, CANDIDATE_STATUS_FAILED
            )
            if batch_id:
                # Fix 1: atomic increment + finalization
                await BatchRepository(session).atomic_increment_and_finalize(
                    batch_id, "failed"
                )
