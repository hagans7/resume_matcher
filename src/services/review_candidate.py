"""ReviewCandidateService — HR manual status override with notes.

Gap fix: status transition validation via adjacency map (O(1) lookup).

Valid transitions (defined in app_constants.VALID_STATUS_TRANSITIONS):
  evaluated → reviewed | rejected
  reviewed  → hired | rejected

HR cannot override back to earlier states (e.g. hired → evaluated).
This enforces a one-way pipeline and prevents accidental data corruption.
"""

from src.core.constants.app_constants import VALID_STATUS_TRANSITIONS
from src.core.exceptions.app_exceptions import (
    CandidateNotFoundError,
    InvalidStatusTransitionError,
)
from src.core.logging.logger import get_logger
from src.entities.candidate import Candidate
from src.interfaces.base_candidate_repository import BaseCandidateRepository

logger = get_logger(__name__)


class ReviewCandidateService:

    def __init__(self, candidate_repo: BaseCandidateRepository) -> None:
        self._repo = candidate_repo

    async def execute(
        self,
        candidate_id: str,
        new_status: str,
        review_notes: str | None = None,
    ) -> Candidate:
        """Update candidate status with HR override. Raises CandidateNotFoundError,
        InvalidStatusTransitionError, PersistenceError.
        """
        # Load current candidate
        candidate = await self._repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(
                f"Candidate not found: {candidate_id}",
                {"candidate_id": candidate_id},
            )

        # Validate transition — O(1) adjacency map lookup
        allowed_next = VALID_STATUS_TRANSITIONS.get(candidate.status, set())
        if new_status not in allowed_next:
            raise InvalidStatusTransitionError(
                f"Cannot transition candidate from {candidate.status!r} to {new_status!r}. "
                f"Allowed transitions: {sorted(allowed_next) or 'none'}",
                {
                    "candidate_id": candidate_id,
                    "current_status": candidate.status,
                    "requested_status": new_status,
                    "allowed": sorted(allowed_next),
                },
            )

        # Persist HR review
        await self._repo.update_review(candidate_id, new_status, review_notes)

        logger.info(
            "candidate_reviewed",
            candidate_id=candidate_id,
            from_status=candidate.status,
            to_status=new_status,
            has_notes=review_notes is not None,
        )

        # Return refreshed entity
        updated = await self._repo.get_by_id(candidate_id)
        return updated
