"""BaseBatchRepository ABC."""

from abc import ABC, abstractmethod

from src.entities.batch import Batch


class BaseBatchRepository(ABC):

    @abstractmethod
    async def create(self, batch: Batch) -> Batch:
        """Persist new batch. Raises PersistenceError."""

    @abstractmethod
    async def get_by_id(self, batch_id: str) -> Batch | None:
        """Return batch or None. Raises PersistenceError."""

    @abstractmethod
    async def increment_succeeded(self, batch_id: str) -> None:
        """Atomic SQL increment: succeeded = succeeded + 1. Raises PersistenceError."""

    @abstractmethod
    async def increment_failed(self, batch_id: str) -> None:
        """Atomic SQL increment: failed = failed + 1. Raises PersistenceError."""

    @abstractmethod
    async def update_status(self, batch_id: str, status: str) -> None:
        """Update batch status. Raises PersistenceError, BatchNotFoundError."""

    @abstractmethod
    async def atomic_increment_and_finalize(
        self,
        batch_id: str,
        field: str,
    ) -> str:
        """Atomically increment succeeded or failed, then set status to completed/partial_failure
        if all items are processed — all in one SQL statement to eliminate race conditions.

        field must be 'succeeded' or 'failed'.
        Returns the batch status after the update (may be unchanged if not yet complete).
        Raises PersistenceError.
        """
