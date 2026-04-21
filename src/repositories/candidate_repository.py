"""CandidateRepository — SQLAlchemy async implementation of BaseCandidateRepository.

Key design notes:
- find_by_hash uses composite unique index (job_id, file_hash) — O(log n) dedup
- update_result implements checkpoint pattern: persists result_json before status
- list_by_job sorts by score DESC NULLS LAST — unevaluated candidates appear at bottom
- count_by_status uses SQL GROUP BY — aggregation at DB level, not Python
- update_review: gap fix — HR override with notes
"""

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.app_exceptions import (
    CandidateNotFoundError,
    DuplicateCVError,
    PersistenceError,
)
from src.core.logging.logger import get_logger
from src.db_models.candidate_orm import CandidateORM
from src.entities.candidate import Candidate
from src.interfaces.base_candidate_repository import BaseCandidateRepository

logger = get_logger(__name__)


class CandidateRepository(BaseCandidateRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, candidate: Candidate) -> Candidate:
        """Persist new candidate. Raises PersistenceError, DuplicateCVError."""
        orm = CandidateORM(
            id=candidate.id,
            job_id=candidate.job_id,
            file_key=candidate.file_key,
            file_hash=candidate.file_hash,
            original_filename=candidate.original_filename,
            status=candidate.status,
            batch_id=candidate.batch_id,
        )
        try:
            self._session.add(orm)
            await self._session.flush()
            await self._session.refresh(orm)
            logger.info("candidate_created", candidate_id=candidate.id, job_id=candidate.job_id)
            return self._to_entity(orm)
        except IntegrityError as exc:
            raise DuplicateCVError(
                "CV already submitted for this job",
                {"job_id": candidate.job_id, "file_hash": candidate.file_hash},
            ) from exc
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to create candidate: {exc}", {"candidate_id": candidate.id}
            ) from exc

    async def get_by_id(self, candidate_id: str) -> Candidate | None:
        """Return candidate or None. Raises PersistenceError."""
        try:
            stmt = select(CandidateORM).where(CandidateORM.id == candidate_id)
            result = await self._session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to fetch candidate: {exc}", {"candidate_id": candidate_id}
            ) from exc

    async def find_by_hash(self, job_id: str, file_hash: str) -> Candidate | None:
        """Duplicate detection via composite unique index. O(log n). Raises PersistenceError."""
        try:
            stmt = select(CandidateORM).where(
                CandidateORM.job_id == job_id,
                CandidateORM.file_hash == file_hash,
            )
            result = await self._session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None
        except SQLAlchemyError as exc:
            raise PersistenceError(f"Failed to check duplicate: {exc}") from exc

    async def update_status(self, candidate_id: str, status: str) -> None:
        """Update status only. Raises PersistenceError."""
        try:
            stmt = (
                update(CandidateORM)
                .where(CandidateORM.id == candidate_id)
                .values(status=status)
            )
            await self._session.execute(stmt)
            logger.debug("candidate_status_updated", candidate_id=candidate_id, status=status)
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to update candidate status: {exc}", {"candidate_id": candidate_id}
            ) from exc

    async def update_result(
        self,
        candidate_id: str,
        score: int,
        verdict: str,
        status: str,
        result_json: dict,
        processing_ms: int,
        token_used: int,
    ) -> None:
        """Persist evaluation result (checkpoint pattern). Raises PersistenceError.

        Two-phase write: result_json persisted first (status unchanged),
        then status updated. If crash between phases, retry detects result_json
        and skips LLM re-execution.
        """
        try:
            # Phase 1: persist result_json (status stays unchanged — checkpoint)
            stmt_checkpoint = (
                update(CandidateORM)
                .where(CandidateORM.id == candidate_id)
                .values(
                    score=score,
                    verdict=verdict,
                    result_json=result_json,
                    processing_ms=processing_ms,
                    token_used=token_used,
                )
            )
            await self._session.execute(stmt_checkpoint)
            await self._session.flush()

            # Phase 2: update status to final value
            stmt_status = (
                update(CandidateORM)
                .where(CandidateORM.id == candidate_id)
                .values(status=status)
            )
            await self._session.execute(stmt_status)

            logger.info(
                "candidate_result_persisted",
                candidate_id=candidate_id,
                score=score,
                verdict=verdict,
                status=status,
                processing_ms=processing_ms,
                token_used=token_used,
            )
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to persist evaluation result: {exc}", {"candidate_id": candidate_id}
            ) from exc

    async def update_review(
        self,
        candidate_id: str,
        status: str,
        review_notes: str | None,
    ) -> None:
        """HR override: update status and review_notes. Raises PersistenceError, CandidateNotFoundError."""
        try:
            stmt = (
                update(CandidateORM)
                .where(CandidateORM.id == candidate_id)
                .values(status=status, review_notes=review_notes)
                .returning(CandidateORM.id)
            )
            result = await self._session.execute(stmt)
            if result.scalar_one_or_none() is None:
                raise CandidateNotFoundError(
                    f"Candidate not found: {candidate_id}", {"candidate_id": candidate_id}
                )
            logger.info(
                "candidate_reviewed",
                candidate_id=candidate_id,
                status=status,
                has_notes=review_notes is not None,
            )
        except CandidateNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to update review: {exc}", {"candidate_id": candidate_id}
            ) from exc

    async def find_existing_hashes(
        self,
        job_id: str,
        file_hashes: list[str],
    ) -> set[str]:
        """Bulk deduplication. O(1) roundtrip via IN query. Raises PersistenceError."""
        if not file_hashes:
            return set()
        try:
            stmt = select(CandidateORM.file_hash).where(
                CandidateORM.job_id == job_id,
                CandidateORM.file_hash.in_(file_hashes),
            )
            result = await self._session.execute(stmt)
            existing = {row.file_hash for row in result.all()}
            logger.debug(
                "bulk_hash_check",
                job_id=job_id,
                checked=len(file_hashes),
                existing=len(existing),
            )
            return existing
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to bulk check hashes: {exc}", {"job_id": job_id}
            ) from exc

    async def list_by_job(
        self,
        job_id: str,
        status_filter: str | None = None,
    ) -> list[Candidate]:
        """List candidates sorted by score desc nulls last. Raises PersistenceError."""
        try:
            stmt = select(CandidateORM).where(CandidateORM.job_id == job_id)
            if status_filter:
                stmt = stmt.where(CandidateORM.status == status_filter)
            stmt = stmt.order_by(CandidateORM.score.desc().nulls_last())
            result = await self._session.execute(stmt)
            return [self._to_entity(orm) for orm in result.scalars().all()]
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to list candidates: {exc}", {"job_id": job_id}
            ) from exc

    async def count_by_status(self, job_id: str) -> dict[str, int]:
        """Aggregate count per status using SQL GROUP BY. Raises PersistenceError."""
        try:
            stmt = (
                select(CandidateORM.status, func.count().label("cnt"))
                .where(CandidateORM.job_id == job_id)
                .group_by(CandidateORM.status)
            )
            result = await self._session.execute(stmt)
            return {row.status: row.cnt for row in result.all()}
        except SQLAlchemyError as exc:
            raise PersistenceError(
                f"Failed to count candidates by status: {exc}", {"job_id": job_id}
            ) from exc

    @staticmethod
    def _to_entity(orm: CandidateORM) -> Candidate:
        return Candidate(
            id=orm.id,
            job_id=orm.job_id,
            file_key=orm.file_key,
            file_hash=orm.file_hash,
            original_filename=orm.original_filename,
            status=orm.status,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            score=orm.score,
            verdict=orm.verdict,
            result_json=orm.result_json,
            processing_ms=orm.processing_ms,
            token_used=orm.token_used,
            batch_id=orm.batch_id,
            review_notes=orm.review_notes,
        )
