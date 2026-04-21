"""Integration tests for JobRepository against real test database."""

from datetime import datetime, timezone

import pytest

from src.entities.job_requirement import JobRequirement
from src.repositories.job_repository import JobRepository


def _make_job(suffix="001") -> JobRequirement:
    return JobRequirement(
        id=f"job-repo-test-{suffix}",
        title=f"Test Job {suffix}",
        description=f"Test job description for repo test {suffix}",
        evaluation_mode="standard",
        status="active",
        created_at=datetime.now(timezone.utc),
    )


class TestJobRepositoryCreate:
    async def test_create_and_get_by_id(self, db_session):
        repo = JobRepository(db_session)
        job = _make_job("create-01")

        created = await repo.create(job)
        assert created.id == job.id
        assert created.title == job.title

        fetched = await repo.get_by_id(job.id)
        assert fetched is not None
        assert fetched.id == job.id
        assert fetched.evaluation_mode == "standard"

    async def test_get_by_id_returns_none_for_missing(self, db_session):
        repo = JobRepository(db_session)
        result = await repo.get_by_id("nonexistent-job-id")
        assert result is None


class TestJobRepositoryListActive:
    async def test_list_active_returns_active_jobs_only(self, db_session):
        repo = JobRepository(db_session)

        active = _make_job("list-active-01")
        archived = _make_job("list-archived-01")
        archived.status = "archived"

        await repo.create(active)
        await repo.create(archived)

        results = await repo.list_active()
        ids = [r.id for r in results]
        assert active.id in ids
        assert archived.id not in ids


class TestJobRepositoryUpdateStatus:
    async def test_update_status_to_archived(self, db_session):
        repo = JobRepository(db_session)
        job = _make_job("status-01")
        await repo.create(job)

        await repo.update_status(job.id, "archived")
        updated = await repo.get_by_id(job.id)
        assert updated.status == "archived"

    async def test_update_status_raises_for_missing_job(self, db_session):
        from src.core.exceptions.app_exceptions import JobNotFoundError
        repo = JobRepository(db_session)
        with pytest.raises(JobNotFoundError):
            await repo.update_status("nonexistent-job", "archived")
