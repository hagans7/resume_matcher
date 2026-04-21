"""ListCandidatesService — returns ranked candidate list for a job."""

from src.core.exceptions.app_exceptions import JobNotFoundError
from src.core.logging.logger import get_logger
from src.entities.candidate import Candidate
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_job_repository import BaseJobRepository

logger = get_logger(__name__)


class ListCandidatesService:

    def __init__(
        self,
        job_repo: BaseJobRepository,
        candidate_repo: BaseCandidateRepository,
    ) -> None:
        self._job_repo = job_repo
        self._candidate_repo = candidate_repo

    async def execute(
        self,
        job_id: str,
        status_filter: str | None = None,
    ) -> list[Candidate]:
        """Return candidates for a job sorted by score desc. Raises JobNotFoundError."""
        job = await self._job_repo.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError(f"Job not found: {job_id}", {"job_id": job_id})

        candidates = await self._candidate_repo.list_by_job(job_id, status_filter)

        logger.debug(
            "candidates_listed",
            job_id=job_id,
            status_filter=status_filter,
            count=len(candidates),
        )
        return candidates
