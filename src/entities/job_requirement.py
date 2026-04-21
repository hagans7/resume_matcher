"""JobRequirement entity.

Represents a job posting with its description and evaluation configuration.
Pure dataclass — zero external imports, no framework coupling.
"""

from dataclasses import dataclass
from datetime import datetime

from src.core.constants.app_constants import JOB_STATUS_ACTIVE


@dataclass
class JobRequirement:
    id: str
    title: str
    description: str
    evaluation_mode: str    # quick | standard | full
    status: str             # active | archived
    created_at: datetime
    created_by: str | None = None

    def is_active(self) -> bool:
        """Check if job is still accepting candidates."""
        return self.status == JOB_STATUS_ACTIVE
