"""CheckBatchStatusService — returns batch progress with per-status candidate counts."""

from src.core.exceptions.app_exceptions import BatchNotFoundError
from src.core.logging.logger import get_logger
from src.entities.batch import Batch
from src.interfaces.base_batch_repository import BaseBatchRepository
from src.interfaces.base_candidate_repository import BaseCandidateRepository

logger = get_logger(__name__)


class CheckBatchStatusService:

    def __init__(
        self,
        batch_repo: BaseBatchRepository,
        candidate_repo: BaseCandidateRepository,
    ) -> None:
        self._batch_repo = batch_repo
        self._candidate_repo = candidate_repo

    async def execute(self, batch_id: str) -> dict:
        """Return batch progress with per-status counts. Raises BatchNotFoundError."""
        batch = await self._batch_repo.get_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundError(f"Batch not found: {batch_id}", {"batch_id": batch_id})

        status_counts = await self._candidate_repo.count_by_status(batch.job_id)

        return {
            "batch_id": batch.id,
            "job_id": batch.job_id,
            "status": batch.status,
            "total": batch.total,
            "succeeded": batch.succeeded,
            "failed": batch.failed,
            "progress_percent": batch.progress_percent(),
            "candidate_counts": status_counts,
        }
