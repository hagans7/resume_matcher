"""CandidateORM — SQLAlchemy model for candidates table.

Gap fixes applied:
- original_filename: human-readable file name for HR display
- review_notes: stores HR override notes

Composite unique index on (job_id, file_hash) prevents duplicate CV submissions
per job. B-tree indexed — O(log n) lookup for duplicate detection.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db_models.base import Base
from src.core.constants.app_constants import CANDIDATE_STATUS_NEW


class CandidateORM(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id"), nullable=True, index=True)

    # File identity
    file_key: Mapped[str] = mapped_column(nullable=False)              # storage path
    file_hash: Mapped[str] = mapped_column(nullable=False)             # SHA-256 for dedup
    original_filename: Mapped[str] = mapped_column(nullable=False)     # e.g. "john_doe_cv.pdf"

    # Evaluation result
    score: Mapped[int | None] = mapped_column(nullable=True)
    verdict: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default=CANDIDATE_STATUS_NEW, nullable=False, index=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(nullable=True)
    token_used: Mapped[int | None] = mapped_column(nullable=True)

    # HR review
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Prevents same CV (by content hash) being submitted twice for the same job.
        UniqueConstraint("job_id", "file_hash", name="uq_candidate_job_file_hash"),
    )

    def __repr__(self) -> str:
        return (
            f"<CandidateORM id={self.id!r} "
            f"filename={self.original_filename!r} "
            f"status={self.status!r} score={self.score}>"
        )
