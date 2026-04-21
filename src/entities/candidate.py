"""Candidate entity.

Represents a CV submission for a specific job.
Carries evaluation result (score, verdict, result_json) once processed.

Gap fixes applied (from blueprint v2 analysis):
- original_filename: human-readable identifier for HR display
- review_notes: stores HR override notes from ReviewCandidateService
"""

from dataclasses import dataclass
from datetime import datetime

from src.core.constants.app_constants import (
    CANDIDATE_STATUS_EVALUATED,
    VERDICT_SHORTLIST,
)


@dataclass
class Candidate:
    id: str
    job_id: str
    file_key: str           # storage path: cv/original/{id}.pdf
    file_hash: str          # SHA-256 hex digest for deduplication
    original_filename: str  # e.g. "john_doe_cv.pdf" — displayed to HR
    status: str             # new | processing | evaluated | reviewed | rejected | hired | failed
    created_at: datetime
    updated_at: datetime
    score: int | None = None
    verdict: str | None = None          # shortlist | review | reject
    result_json: dict | None = None     # full EvaluationResult serialized as JSONB
    processing_ms: int | None = None    # total wall-clock time for evaluation
    token_used: int | None = None       # LLM tokens consumed
    batch_id: str | None = None         # set if submitted via batch
    review_notes: str | None = None     # HR override notes from review endpoint

    def is_evaluated(self) -> bool:
        """Check if AI evaluation is complete."""
        return self.status == CANDIDATE_STATUS_EVALUATED

    def is_shortlisted(self) -> bool:
        """Check if AI verdict is shortlist."""
        return self.verdict == VERDICT_SHORTLIST
