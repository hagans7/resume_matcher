"""BatchORM — SQLAlchemy model for batches table.

Note on migration order:
batches table must be created BEFORE candidates table
because candidates.batch_id references batches.id (FK).
Alembic autogenerate handles this via dependency resolution.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db_models.base import Base
from src.core.constants.app_constants import BATCH_STATUS_QUEUED


class BatchORM(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    total: Mapped[int] = mapped_column(nullable=False)
    succeeded: Mapped[int] = mapped_column(default=0, nullable=False)
    failed: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(default=BATCH_STATUS_QUEUED, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<BatchORM id={self.id!r} "
            f"status={self.status!r} "
            f"total={self.total} "
            f"succeeded={self.succeeded} failed={self.failed}>"
        )
