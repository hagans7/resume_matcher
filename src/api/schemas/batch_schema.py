"""Batch API schemas."""

from datetime import datetime

from pydantic import BaseModel


class BatchSubmitResponse(BaseModel):
    batch_id: str
    job_id: str
    status: str
    total: int
    message: str = "Batch queued for processing."


class BatchStatusResponse(BaseModel):
    batch_id: str
    job_id: str
    status: str
    total: int
    succeeded: int
    failed: int
    progress_percent: int
    candidate_counts: dict[str, int]
