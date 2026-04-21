"""Candidate API schemas."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from src.core.constants.app_constants import VALID_STATUS_TRANSITIONS


class CandidateSummary(BaseModel):
    id: str
    job_id: str
    original_filename: str
    score: int | None = None
    verdict: str | None = None
    status: str
    processing_ms: int | None = None
    token_used: int | None = None
    batch_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(BaseModel):
    candidates: list[CandidateSummary]
    total: int


class CandidateDetailResponse(BaseModel):
    id: str
    job_id: str
    original_filename: str
    file_hash: str
    score: int | None = None
    verdict: str | None = None
    status: str
    result: dict | None = None         # full result_json from DB
    review_notes: str | None = None
    processing_ms: int | None = None
    token_used: int | None = None
    batch_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewRequest(BaseModel):
    status: str
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_target_status(cls, v: str) -> str:
        # Collect all valid target statuses across all transitions
        all_targets = {s for targets in VALID_STATUS_TRANSITIONS.values() for s in targets}
        if v not in all_targets:
            raise ValueError(
                f"Invalid review status: {v!r}. "
                f"Valid targets: {sorted(all_targets)}"
            )
        return v


class ReviewResponse(BaseModel):
    candidate_id: str
    previous_status: str
    new_status: str
    review_notes: str | None = None
