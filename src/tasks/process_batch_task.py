"""process_batch — Celery fan-out task that enqueues per-CV evaluations.

Fix 2: uses shared _async_session_factory from evaluate_single_task
instead of creating a new async engine per call.

Called once per batch submission. Loads all new candidates for the batch
and enqueues one evaluate_single task per candidate.

O(n) enqueue operations where n = batch size.
Each evaluation runs independently — failures are isolated per candidate.
"""

import asyncio

from src.core.constants.app_constants import BATCH_STATUS_PROCESSING, CANDIDATE_STATUS_NEW
from src.core.config.settings import settings
from src.core.logging.logger import get_logger, setup_logging
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="tasks.process_batch")
def process_batch(batch_id: str) -> dict:
    """Load batch, update status to processing, enqueue one task per candidate."""
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("process_batch_started", batch_id=batch_id)
    return asyncio.run(_run(batch_id))


async def _run(batch_id: str) -> dict:
    # Fix 2: reuse shared engine from evaluate_single_task — no new engine created
    from src.tasks.evaluate_single_task import _async_session_factory
    from src.repositories.batch_repository import BatchRepository
    from src.repositories.candidate_repository import CandidateRepository
    from src.tasks.evaluate_single_task import evaluate_single

    async with _async_session_factory() as session:
        async with session.begin():
            batch_repo = BatchRepository(session)
            candidate_repo = CandidateRepository(session)

            await batch_repo.update_status(batch_id, BATCH_STATUS_PROCESSING)

            batch = await batch_repo.get_by_id(batch_id)
            if batch is None:
                logger.error("process_batch_not_found", batch_id=batch_id)
                return {"batch_id": batch_id, "enqueued": 0}

            # Load candidates for this batch that are still new
            all_candidates = await candidate_repo.list_by_job(
                job_id=batch.job_id,
                status_filter=CANDIDATE_STATUS_NEW,
            )
            batch_candidates = [c for c in all_candidates if c.batch_id == batch_id]

            for candidate in batch_candidates:
                evaluate_single.delay(
                    candidate_id=candidate.id,
                    batch_id=batch_id,
                )

            logger.info(
                "process_batch_enqueued",
                batch_id=batch_id,
                enqueued=len(batch_candidates),
            )

    return {"batch_id": batch_id, "enqueued": len(batch_candidates)}
