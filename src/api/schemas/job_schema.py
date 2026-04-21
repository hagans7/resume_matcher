"""Job API schemas — request/response for job management endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.core.constants.app_constants import (
    EVALUATION_MODE_STANDARD,
    VALID_EVALUATION_MODES,
)


class CreateJobRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10)
    evaluation_mode: str = Field(default=EVALUATION_MODE_STANDARD)

    @field_validator("evaluation_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in VALID_EVALUATION_MODES:
            raise ValueError(f"Must be one of: {sorted(VALID_EVALUATION_MODES)}")
        return v
class JobResponse(BaseModel):
    id: str
    title: str
    description: str
    evaluation_mode: str
    status: str
    created_at: datetime
    created_by: str | None = None

class UpdateJobRequest(BaseModel):
    """Request body for PUT /jobs/{job_id} — update title and/or description."""
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10)