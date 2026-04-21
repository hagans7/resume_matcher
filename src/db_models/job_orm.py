"""JobORM — SQLAlchemy model for jobs table."""

from datetime import datetime

from sqlalchemy import Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db_models.base import Base
from src.core.constants.app_constants import (
    EVALUATION_MODE_STANDARD,
    JOB_STATUS_ACTIVE,
)


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_mode: Mapped[str] = mapped_column(default=EVALUATION_MODE_STANDARD, nullable=False)
    status: Mapped[str] = mapped_column(default=JOB_STATUS_ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<JobORM id={self.id!r} title={self.title!r} status={self.status!r}>"
