"""BatchRepository — SQLAlchemy async implementation of BaseBatchRepository.
"""

from sqlalchemy import case, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants.app_constants import (
    BATCH_STATUS_COMPLETED,
    BATCH_STATUS_PARTIAL_FAILURE,
)
from src.core.exceptions.app_exceptions import BatchNotFoundError, PersistenceError
from src.core.logging.logger import get_logger
from src.db_models.batch_orm import BatchORM
from src.db_models.candidate_orm import CandidateORM
from src.entities.batch import Batch
from src.interfaces.base_batch_repository import BaseBatchRepository

logger = get_logger(__name__)


class BatchRepository(BaseBatchRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, batch: Batch) -> Batch:
        """Persist new batch. Raises PersistenceError."""
        orm = BatchORM(
            id=batch.id,
            job_id=batch.job_id,
            total=batch.total,
            succeeded=batch.succeeded,
            failed=batch.failed,
            status=batch.status,
        )
        try:
            self._session.add(orm)
            await self._session.flush()
            await self._session.refresh(orm)
            logger.info("batch_created", batch_id=batch.id, job_id=batch.job_id, total=batch.total)
            return self._to_entity(orm)
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to create batch: {exc}", {"batch_id": batch.id}
            ) from exc

    async def get_by_id(self, batch_id: str) -> Batch | None:
        """Return batch or None. Raises PersistenceError."""
        try:
            stmt = select(BatchORM).where(BatchORM.id == batch_id)
            result = await self._session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to fetch batch: {exc}", {"batch_id": batch_id}
            ) from exc

    async def increment_succeeded(self, batch_id: str) -> None:
        """Atomic SQL increment for single-CV flow. Raises PersistenceError."""
        try:
            stmt = (
                update(BatchORM)
                .where(BatchORM.id == batch_id)
                .values(succeeded=BatchORM.succeeded + 1)
            )
            await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to increment batch succeeded: {exc}", {"batch_id": batch_id}
            ) from exc

    async def increment_failed(self, batch_id: str) -> None:
        """Atomic SQL increment for single-CV flow. Raises PersistenceError."""
        try:
            stmt = (
                update(BatchORM)
                .where(BatchORM.id == batch_id)
                .values(failed=BatchORM.failed + 1)
            )
            await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to increment batch failed: {exc}", {"batch_id": batch_id}
            ) from exc

    async def update_status(self, batch_id: str, status: str) -> None:
        """Update batch status. Raises PersistenceError, BatchNotFoundError."""
        try:
            stmt = (
                update(BatchORM)
                .where(BatchORM.id == batch_id)
                .values(status=status)
                .returning(BatchORM.id)
            )
            result = await self._session.execute(stmt)
            if result.scalar_one_or_none() is None:
                raise BatchNotFoundError(f"Batch not found: {batch_id}", {"batch_id": batch_id})
            logger.info("batch_status_updated", batch_id=batch_id, status=status)
        except BatchNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to update batch status: {exc}", {"batch_id": batch_id}
            ) from exc

    async def atomic_increment_and_finalize(
        self,
        batch_id: str,
        field: str,
    ) -> str:
        """Fix 1 — Race condition elimination.

        Increment succeeded or failed AND conditionally set final status
        in a SINGLE SQL statement. No Python-layer read-then-write window.

        SQL logic (pseudocode):
          new_succeeded = succeeded + (1 if field=='succeeded' else 0)
          new_failed    = failed    + (1 if field=='failed'    else 0)
          new_status    = CASE
            WHEN new_succeeded + new_failed >= total THEN
              CASE WHEN new_failed > 0 THEN 'partial_failure' ELSE 'completed' END
            ELSE current_status
          END

        Returns the status value AFTER the update.
        Raises PersistenceError, BatchNotFoundError.
        """
        if field not in ("succeeded", "failed"):
            raise ValueError(f"field must be 'succeeded' or 'failed', got: {field!r}")

        succ_delta = 1 if field == "succeeded" else 0
        fail_delta = 1 if field == "failed" else 0

        new_succ = BatchORM.succeeded + succ_delta
        new_fail = BatchORM.failed + fail_delta
        new_processed = new_succ + new_fail

        # Nested CASE: if done → pick completed/partial_failure, else keep current
        new_status = case(
            (new_processed >= BatchORM.total,
             case(
                 (new_fail > 0, BATCH_STATUS_PARTIAL_FAILURE),
                 else_=BATCH_STATUS_COMPLETED,
             )),
            else_=BatchORM.status,
        )

        try:
            stmt = (
                update(BatchORM)
                .where(BatchORM.id == batch_id)
                .values(
                    succeeded=new_succ,
                    failed=new_fail,
                    status=new_status,
                )
                .returning(
                    BatchORM.status,
                    BatchORM.succeeded,
                    BatchORM.failed,
                    BatchORM.total,
                )
            )
            result = await self._session.execute(stmt)
            row = result.one_or_none()

            if row is None:
                raise BatchNotFoundError(
                    f"Batch not found: {batch_id}", {"batch_id": batch_id}
                )

            final_status, succeeded, failed, total = row
            logger.info(
                "batch_atomic_increment",
                batch_id=batch_id,
                field=field,
                succeeded=succeeded,
                failed=failed,
                total=total,
                status=final_status,
            )
            return final_status

        except BatchNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to atomically increment batch: {exc}", {"batch_id": batch_id}
            ) from exc

    @staticmethod
    def _to_entity(orm: BatchORM) -> Batch:
        return Batch(
            id=orm.id,
            job_id=orm.job_id,
            total=orm.total,
            succeeded=orm.succeeded,
            failed=orm.failed,
            status=orm.status,
            created_at=orm.created_at,
        )
