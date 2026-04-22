"""BaseJobRepository ABC."""

from abc import ABC, abstractmethod

from src.entities.job_requirement import JobRequirement


class BaseJobRepository(ABC):

    @abstractmethod
    async def create(self, job: JobRequirement) -> JobRequirement:
        """Persist new job. Raises PersistenceError."""

    @abstractmethod
    async def get_by_id(self, job_id: str) -> JobRequirement | None:
        """Return job or None if not found. Raises PersistenceError."""

    @abstractmethod
    async def list_active(self) -> list[JobRequirement]:
        """Return all jobs with status=active ordered by created_at desc. Raises PersistenceError."""

    @abstractmethod
    async def update_status(self, job_id: str, status: str) -> None:
        """Update job status field. Raises PersistenceError, JobNotFoundError."""

    @abstractmethod
    async def update(self, job_id: str, title: str, description: str) -> JobRequirement:
        """Update job title and description. Raises PersistenceError, JobNotFoundError."""
