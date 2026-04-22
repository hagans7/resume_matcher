"""DeleteCandidateService — hard delete candidate with cascading storage cleanup.

Steps:
  1. Fetch candidate — raise CandidateNotFoundError if not found
  2. Delete original CV from storage (cv/original/...)
  3. Delete parsed text from storage (cv/parsed/...)
  4. Delete evaluation report from storage (reports/...)
  5. Hard delete DB record

Storage failures are logged but do not abort the DB delete.
This ensures DB is always cleaned up even if storage is partially unavailable.
"""

from pathlib import Path

from src.core.exceptions.app_exceptions import CandidateNotFoundError
from src.core.logging.logger import get_logger
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_storage_client import BaseStorageClient

logger = get_logger(__name__)


class DeleteCandidateService:

    def __init__(
        self,
        candidate_repo: BaseCandidateRepository,
        storage: BaseStorageClient,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._storage = storage

    async def execute(self, candidate_id: str) -> None:
        """Delete candidate and all associated files. Raises CandidateNotFoundError."""
        # 1. Fetch to get file_key and verify existence
        candidate = await self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(
                f"Candidate not found: {candidate_id}",
                {"candidate_id": candidate_id},
            )

        # 2. Derive storage keys from file_key
        # file_key pattern: cv/original/{candidate_id}.{ext}
        # parsed pattern:   cv/parsed/{candidate_id}.txt
        # report pattern:   reports/{candidate_id}.md
        stem = Path(candidate.file_key).stem  # candidate_id without extension
        keys_to_delete = [
            candidate.file_key,                    # original CV
            f"cv/parsed/{stem}.txt",               # extracted text
            f"reports/{stem}.md",                  # evaluation report
        ]

        # 3. Delete storage files — non-fatal, log failures
        for key in keys_to_delete:
            try:
                await self._storage.delete(key)
                logger.debug("candidate_file_deleted", candidate_id=candidate_id, key=key)
            except Exception as exc:
                logger.warning(
                    "candidate_file_delete_failed",
                    candidate_id=candidate_id,
                    key=key,
                    error=str(exc),
                )

        # 4. Hard delete DB record
        await self._candidate_repo.delete(candidate_id)

        logger.info(
            "candidate_deleted",
            candidate_id=candidate_id,
            job_id=candidate.job_id,
            files_attempted=len(keys_to_delete),
        )