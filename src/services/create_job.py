"""CreateJobService — creates a new job requirement record."""

import uuid
from datetime import datetime, timezone

from src.core.constants.app_constants import (
    EVALUATION_MODE_STANDARD,
    JOB_STATUS_ACTIVE,
    VALID_EVALUATION_MODES,
)
from src.core.exceptions.app_exceptions import ValidationError
from src.core.logging.logger import get_logger
from src.entities.job_requirement import JobRequirement
from src.interfaces.base_job_repository import BaseJobRepository

logger = get_logger(__name__)


class CreateJobService:

    def __init__(self, job_repo: BaseJobRepository) -> None:
        self._repo = job_repo

    async def execute(
        self,
        title: str,
        description: str,
        evaluation_mode: str = EVALUATION_MODE_STANDARD,
        created_by: str | None = None,
    ) -> JobRequirement:
        """Create and persist a new job requirement. Raises ValidationError, PersistenceError."""
        if evaluation_mode not in VALID_EVALUATION_MODES:
            raise ValidationError(
                f"Invalid evaluation_mode: {evaluation_mode!r}. "
                f"Must be one of: {sorted(VALID_EVALUATION_MODES)}",
                {"evaluation_mode": evaluation_mode},
            )

        if not title.strip():
            raise ValidationError("Job title cannot be empty.")

        if not description.strip():
            raise ValidationError("Job description cannot be empty.")

        job = JobRequirement(
            id=str(uuid.uuid4()),
            title=title.strip(),
            description=description.strip(),
            evaluation_mode=evaluation_mode,
            status=JOB_STATUS_ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
        )

        created = await self._repo.create(job)
        logger.info(
            "job_created",
            job_id=created.id,
            title=created.title,
            mode=evaluation_mode,
        )
        return created
