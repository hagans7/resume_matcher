"""Integration tests for BatchRepository — atomic increment and bulk hash lookup."""

from datetime import datetime, timezone

import pytest

from src.core.constants.app_constants import (
    BATCH_STATUS_COMPLETED,
    BATCH_STATUS_PARTIAL_FAILURE,
    BATCH_STATUS_PROCESSING,
)
from src.entities.batch import Batch
from src.repositories.batch_repository import BatchRepository
from src.repositories.candidate_repository import CandidateRepository
from src.repositories.job_repository import JobRepository
from src.entities.job_requirement import JobRequirement
from src.entities.candidate import Candidate


def _make_batch(batch_id: str, job_id: str, total: int) -> Batch:
    return Batch(
        id=batch_id,
        job_id=job_id,
        total=total,
        status=BATCH_STATUS_PROCESSING,
        created_at=datetime.now(timezone.utc),
    )


def _make_job(job_id: str) -> JobRequirement:
    return JobRequirement(
        id=job_id,
        title="Test Job",
        description="Test job for repo integration tests",
        evaluation_mode="standard",
        status="active",
        created_at=datetime.now(timezone.utc),
    )


class TestAtomicIncrementAndFinalize:
    async def test_increment_succeeded_returns_processing_when_not_done(self, db_session):
        job_repo = JobRepository(db_session)
        batch_repo = BatchRepository(db_session)

        job = await job_repo.create(_make_job("j-atomic-01"))
        batch = await batch_repo.create(_make_batch("b-atomic-01", job.id, total=3))

        status = await batch_repo.atomic_increment_and_finalize("b-atomic-01", "succeeded")
        assert status == BATCH_STATUS_PROCESSING  # 1/3 done, not yet complete

    async def test_last_increment_triggers_completed(self, db_session):
        job_repo = JobRepository(db_session)
        batch_repo = BatchRepository(db_session)

        job = await job_repo.create(_make_job("j-atomic-02"))
        batch = await batch_repo.create(_make_batch("b-atomic-02", job.id, total=2))

        # First increment — still processing
        await batch_repo.atomic_increment_and_finalize("b-atomic-02", "succeeded")
        # Second increment — should complete
        status = await batch_repo.atomic_increment_and_finalize("b-atomic-02", "succeeded")
        assert status == BATCH_STATUS_COMPLETED

    async def test_failure_triggers_partial_failure(self, db_session):
        job_repo = JobRepository(db_session)
        batch_repo = BatchRepository(db_session)

        job = await job_repo.create(_make_job("j-atomic-03"))
        batch = await batch_repo.create(_make_batch("b-atomic-03", job.id, total=2))

        await batch_repo.atomic_increment_and_finalize("b-atomic-03", "succeeded")
        status = await batch_repo.atomic_increment_and_finalize("b-atomic-03", "failed")
        assert status == BATCH_STATUS_PARTIAL_FAILURE

    async def test_invalid_field_raises_value_error(self, db_session):
        batch_repo = BatchRepository(db_session)
        with pytest.raises(ValueError, match="succeeded.*failed"):
            await batch_repo.atomic_increment_and_finalize("any-id", "invalid_field")


class TestFindExistingHashesOnCandidateRepo:
    async def test_returns_empty_set_for_empty_input(self, db_session):
        repo = CandidateRepository(db_session)
        result = await repo.find_existing_hashes("job-001", [])
        assert result == set()

    async def test_returns_matching_hashes(self, db_session):
        job_repo = JobRepository(db_session)
        candidate_repo = CandidateRepository(db_session)
        batch_repo = BatchRepository(db_session)

        job = await job_repo.create(_make_job("j-hash-01"))
        batch = await batch_repo.create(_make_batch("b-hash-01", job.id, 2))

        # Create a candidate with known hash
        from src.core.constants.app_constants import CANDIDATE_STATUS_NEW
        c = Candidate(
            id="cand-hash-01",
            job_id=job.id,
            file_key="cv/original/cand-hash-01.pdf",
            file_hash="knownhash123abc",
            original_filename="test.pdf",
            status=CANDIDATE_STATUS_NEW,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            batch_id=batch.id,
        )
        await candidate_repo.create(c)

        # Query with known + unknown hash
        existing = await candidate_repo.find_existing_hashes(
            job.id, ["knownhash123abc", "unknownhash456"]
        )
        assert existing == {"knownhash123abc"}

    async def test_does_not_match_different_job(self, db_session):
        """Hash dedup is job-scoped — same hash for different job should not match."""
        job_repo = JobRepository(db_session)
        candidate_repo = CandidateRepository(db_session)
        batch_repo = BatchRepository(db_session)

        job1 = await job_repo.create(_make_job("j-hash-02"))
        job2 = await job_repo.create(_make_job("j-hash-03"))
        batch1 = await batch_repo.create(_make_batch("b-hash-02", job1.id, 1))

        from src.core.constants.app_constants import CANDIDATE_STATUS_NEW
        c = Candidate(
            id="cand-hash-02",
            job_id=job1.id,
            file_key="cv/original/cand-hash-02.pdf",
            file_hash="sharedhash789",
            original_filename="test.pdf",
            status=CANDIDATE_STATUS_NEW,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            batch_id=batch1.id,
        )
        await candidate_repo.create(c)

        # Query from job2's perspective — should not see job1's candidate
        existing = await candidate_repo.find_existing_hashes(job2.id, ["sharedhash789"])
        assert existing == set()
