"""CancelBatchService — cancel a queued or processing batch.

Cancellation sets batch status to 'cancelled'.
The Celery worker checks this status before executing each task
and skips evaluation if batch is already cancelled.
"""

from src.core.constants.app_constants import (
    BATCH_STATUS_CANCELLED,
    BATCH_STATUS_PROCESSING,
    BATCH_STATUS_QUEUED,
)
from src.core.exceptions.app_exceptions import BatchNotFoundError, ValidationError
from src.core.logging.logger import get_logger
from src.interfaces.base_batch_repository import BaseBatchRepository

logger = get_logger(__name__)

# Only these statuses can be cancelled — completed/failed batches cannot be undone
CANCELLABLE_STATUSES = {BATCH_STATUS_QUEUED, BATCH_STATUS_PROCESSING}


class CancelBatchService:

    def __init__(self, batch_repo: BaseBatchRepository) -> None:
        self._batch_repo = batch_repo

    async def execute(self, batch_id: str) -> None:
        """Cancel a batch. Raises BatchNotFoundError, ValidationError."""
        batch = await self._batch_repo.get_by_id(batch_id)
        if batch is None:
            raise BatchNotFoundError(f"Batch not found: {batch_id}", {"batch_id": batch_id})

        if batch.status not in CANCELLABLE_STATUSES:
            raise ValidationError(
                f"Batch {batch_id!r} cannot be cancelled — current status: {batch.status!r}. "
                f"Only {sorted(CANCELLABLE_STATUSES)} batches can be cancelled.",
                {"batch_id": batch_id, "current_status": batch.status},
            )

        await self._batch_repo.update_status(batch_id, BATCH_STATUS_CANCELLED)

        logger.info(
            "batch_cancelled",
            batch_id=batch_id,
            previous_status=batch.status,
            total=batch.total,
        )