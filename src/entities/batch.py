"""Batch entity.

Represents a bulk CV submission job. Tracks aggregate progress
across all candidate evaluations spawned from this batch.
"""

from dataclasses import dataclass
from datetime import datetime

from src.core.constants.app_constants import BATCH_STATUS_COMPLETED, BATCH_STATUS_PARTIAL_FAILURE


@dataclass
class Batch:
    id: str
    job_id: str
    total: int
    status: str             # queued | processing | completed | partial_failure
    created_at: datetime
    succeeded: int = 0
    failed: int = 0

    def progress_percent(self) -> int:
        """Calculate completion percentage. Returns 0 if total is 0."""
        if self.total == 0:
            return 0
        return round((self.succeeded + self.failed) / self.total * 100)

    def is_complete(self) -> bool:
        """Check if all candidates have been processed (success or failure)."""
        return (self.succeeded + self.failed) >= self.total

    def resolve_final_status(self) -> str:
        """Return appropriate final status based on failure count. Raises if not complete."""
        if not self.is_complete():
            raise ValueError("Cannot resolve final status: batch is not complete yet.")
        if self.failed == 0:
            return BATCH_STATUS_COMPLETED
        return BATCH_STATUS_PARTIAL_FAILURE
