"""Repository providers — one per repository, each depends on DB session."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.interfaces.base_batch_repository import BaseBatchRepository
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_job_repository import BaseJobRepository
from src.providers.infrastructure import get_db_session
from src.repositories.batch_repository import BatchRepository
from src.repositories.candidate_repository import CandidateRepository
from src.repositories.job_repository import JobRepository


def get_job_repo(
    db: AsyncSession = Depends(get_db_session),
) -> BaseJobRepository:
    return JobRepository(db)


def get_candidate_repo(
    db: AsyncSession = Depends(get_db_session),
) -> BaseCandidateRepository:
    return CandidateRepository(db)


def get_batch_repo(
    db: AsyncSession = Depends(get_db_session),
) -> BaseBatchRepository:
    return BatchRepository(db)
