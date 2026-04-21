"""JobRepository — SQLAlchemy async implementation of BaseJobRepository."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.app_exceptions import JobNotFoundError, PersistenceError
from src.core.logging.logger import get_logger
from src.db_models.job_orm import JobORM
from src.entities.job_requirement import JobRequirement
from src.interfaces.base_job_repository import BaseJobRepository

logger = get_logger(__name__)


class JobRepository(BaseJobRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job: JobRequirement) -> JobRequirement:
        """Persist new job. Raises PersistenceError."""
        orm = JobORM(
            id=job.id,
            title=job.title,
            description=job.description,
            evaluation_mode=job.evaluation_mode,
            status=job.status,
            created_by=job.created_by,
        )
        try:
            self._session.add(orm)
            await self._session.flush()
            await self._session.refresh(orm)
            logger.info("job_created", job_id=job.id, title=job.title)
            return self._to_entity(orm)
        except SQLAlchemyError as exc:
            raise PersistenceError(f"Failed to create job: {exc}", {"job_id": job.id}) from exc

    async def get_by_id(self, job_id: str) -> JobRequirement | None:
        """Return job or None if not found. Raises PersistenceError."""
        try:
            stmt = select(JobORM).where(JobORM.id == job_id)
            result = await self._session.execute(stmt)
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None
        except SQLAlchemyError as exc:
            raise PersistenceError(f"Failed to fetch job: {exc}", {"job_id": job_id}) from exc

    async def list_active(self) -> list[JobRequirement]:
        """Return all active jobs ordered by created_at desc. Raises PersistenceError."""
        try:
            stmt = (
                select(JobORM)
                .where(JobORM.status == "active")
                .order_by(JobORM.created_at.desc())
            )
            result = await self._session.execute(stmt)
            return [self._to_entity(orm) for orm in result.scalars().all()]
        except SQLAlchemyError as exc:
            raise PersistenceError(f"Failed to list jobs: {exc}") from exc

    async def update_status(self, job_id: str, status: str) -> None:
        """Update job status. Raises PersistenceError, JobNotFoundError."""
        try:
            stmt = (
                update(JobORM)
                .where(JobORM.id == job_id)
                .values(status=status)
                .returning(JobORM.id)
            )
            result = await self._session.execute(stmt)
            if result.scalar_one_or_none() is None:
                raise JobNotFoundError(f"Job not found: {job_id}", {"job_id": job_id})
            logger.info("job_status_updated", job_id=job_id, status=status)
        except JobNotFoundError:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceError(f"Failed to update job status: {exc}", {"job_id": job_id}) from exc

    @staticmethod
    def _to_entity(orm: JobORM) -> JobRequirement:
        return JobRequirement(
            id=orm.id,
            title=orm.title,
            description=orm.description,
            evaluation_mode=orm.evaluation_mode,
            status=orm.status,
            created_at=orm.created_at,
            created_by=orm.created_by,
        )
