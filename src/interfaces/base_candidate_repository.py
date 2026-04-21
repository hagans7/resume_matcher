"""BaseCandidateRepository ABC.

Gap fix: update_review() added to support HR status override with notes.
"""

from abc import ABC, abstractmethod

from src.entities.candidate import Candidate


class BaseCandidateRepository(ABC):

    @abstractmethod
    async def create(self, candidate: Candidate) -> Candidate:
        """Persist new candidate. Raises PersistenceError, DuplicateCVError."""

    @abstractmethod
    async def get_by_id(self, candidate_id: str) -> Candidate | None:
        """Return candidate or None. Raises PersistenceError."""

    @abstractmethod
    async def find_by_hash(self, job_id: str, file_hash: str) -> Candidate | None:
        """Duplicate detection via composite unique index. O(log n). Raises PersistenceError."""

    @abstractmethod
    async def update_status(self, candidate_id: str, status: str) -> None:
        """Update status only. Used for processing state transitions. Raises PersistenceError."""

    @abstractmethod
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
        """Persist evaluation result (checkpoint pattern). Raises PersistenceError."""

    @abstractmethod
    async def update_review(
        self,
        candidate_id: str,
        status: str,
        review_notes: str | None,
    ) -> None:
        """HR override: update status and review_notes. Raises PersistenceError, CandidateNotFoundError."""

    @abstractmethod
    async def delete(self, candidate_id: str) -> None:
        """Hard delete candidate record. Raises PersistenceError, CandidateNotFoundError."""
        
    @abstractmethod
    async def find_existing_hashes(
        self,
        job_id: str,
        file_hashes: list[str],
    ) -> set[str]:
        """Bulk deduplication: return subset of file_hashes already submitted for this job.

        Single O(1) roundtrip: WHERE file_hash IN (...).
        Empty input returns empty set with no DB call.
        Raises PersistenceError.
        """

    @abstractmethod
    async def list_by_job(
        self,
        job_id: str,
        status_filter: str | None = None,
    ) -> list[Candidate]:
        """List candidates for a job, sorted by score desc. Optionally filtered by status. Raises PersistenceError."""

    @abstractmethod
    async def count_by_status(self, job_id: str) -> dict[str, int]:
        """Aggregate candidate count per status for a job. SQL GROUP BY at DB level. Raises PersistenceError."""
