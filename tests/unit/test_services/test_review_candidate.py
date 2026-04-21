"""Unit tests for ReviewCandidateService — status transition validation."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.exceptions.app_exceptions import (
    CandidateNotFoundError,
    InvalidStatusTransitionError,
)
from src.entities.candidate import Candidate
from src.services.review_candidate import ReviewCandidateService


def _make_candidate(status: str) -> Candidate:
    return Candidate(
        id="cand-001",
        job_id="job-001",
        file_key="cv/original/cand-001.pdf",
        file_hash="abc" * 20,
        original_filename="test.pdf",
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def svc(repo):
    return ReviewCandidateService(candidate_repo=repo)


class TestValidTransitions:
    async def test_evaluated_to_reviewed(self, svc, repo):
        candidate = _make_candidate("evaluated")
        updated = _make_candidate("reviewed")
        repo.get_by_id.side_effect = [candidate, updated]
        repo.update_review.return_value = None

        result = await svc.execute("cand-001", "reviewed", "Strong Python skills")
        repo.update_review.assert_called_once_with("cand-001", "reviewed", "Strong Python skills")
        assert result.status == "reviewed"

    async def test_evaluated_to_rejected(self, svc, repo):
        candidate = _make_candidate("evaluated")
        updated = _make_candidate("rejected")
        repo.get_by_id.side_effect = [candidate, updated]
        repo.update_review.return_value = None

        result = await svc.execute("cand-001", "rejected")
        assert result.status == "rejected"

    async def test_reviewed_to_hired(self, svc, repo):
        candidate = _make_candidate("reviewed")
        updated = _make_candidate("hired")
        repo.get_by_id.side_effect = [candidate, updated]
        repo.update_review.return_value = None

        result = await svc.execute("cand-001", "hired")
        assert result.status == "hired"

    async def test_reviewed_to_rejected(self, svc, repo):
        candidate = _make_candidate("reviewed")
        updated = _make_candidate("rejected")
        repo.get_by_id.side_effect = [candidate, updated]
        repo.update_review.return_value = None

        result = await svc.execute("cand-001", "rejected")
        assert result.status == "rejected"


class TestInvalidTransitions:
    async def test_new_cannot_be_reviewed(self, svc, repo):
        repo.get_by_id.return_value = _make_candidate("new")
        with pytest.raises(InvalidStatusTransitionError):
            await svc.execute("cand-001", "reviewed")

    async def test_hired_cannot_go_back(self, svc, repo):
        repo.get_by_id.return_value = _make_candidate("hired")
        with pytest.raises(InvalidStatusTransitionError):
            await svc.execute("cand-001", "evaluated")

    async def test_processing_cannot_be_shortlisted(self, svc, repo):
        repo.get_by_id.return_value = _make_candidate("processing")
        with pytest.raises(InvalidStatusTransitionError):
            await svc.execute("cand-001", "reviewed")


class TestNotFound:
    async def test_raises_when_candidate_missing(self, svc, repo):
        repo.get_by_id.return_value = None
        with pytest.raises(CandidateNotFoundError):
            await svc.execute("nonexistent", "reviewed")
