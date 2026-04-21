"""Unit tests for DeleteCandidateService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, call

import pytest

from src.core.exceptions.app_exceptions import CandidateNotFoundError
from src.entities.candidate import Candidate
from src.services.delete_candidate import DeleteCandidateService


def _make_candidate(candidate_id="cand-001", file_key="cv/original/cand-001.pdf") -> Candidate:
    return Candidate(
        id=candidate_id,
        job_id="job-001",
        file_key=file_key,
        file_hash="abc123",
        original_filename="cv.pdf",
        status="evaluated",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def candidate_repo():
    repo = AsyncMock()
    repo.get_by_id.return_value = _make_candidate()
    repo.delete.return_value = None
    return repo


@pytest.fixture
def storage():
    s = AsyncMock()
    s.delete.return_value = None
    return s


@pytest.fixture
def svc(candidate_repo, storage):
    return DeleteCandidateService(candidate_repo=candidate_repo, storage=storage)


class TestDeleteCandidateSuccess:
    async def test_deletes_db_record(self, svc, candidate_repo):
        await svc.execute("cand-001")
        candidate_repo.delete.assert_called_once_with("cand-001")

    async def test_deletes_all_three_storage_keys(self, svc, storage):
        await svc.execute("cand-001")
        deleted_keys = [c.args[0] for c in storage.delete.call_args_list]
        assert "cv/original/cand-001.pdf" in deleted_keys
        assert "cv/parsed/cand-001.txt" in deleted_keys
        assert "reports/cand-001.md" in deleted_keys

    async def test_storage_delete_called_before_db_delete(self, svc, candidate_repo, storage):
        """Storage cleanup must happen before DB delete to avoid orphaned files."""
        call_order = []
        storage.delete.side_effect = lambda k: call_order.append(f"storage:{k}")
        candidate_repo.delete.side_effect = lambda cid: call_order.append(f"db:{cid}")
        # Make side_effect return coroutines
        async def mock_storage_delete(key):
            call_order.append(f"storage:{key}")
        async def mock_db_delete(cid):
            call_order.append(f"db:{cid}")
        storage.delete.side_effect = mock_storage_delete
        candidate_repo.delete.side_effect = mock_db_delete

        await svc.execute("cand-001")

        # All storage deletes must come before DB delete
        db_index = next(i for i, c in enumerate(call_order) if c.startswith("db:"))
        storage_indices = [i for i, c in enumerate(call_order) if c.startswith("storage:")]
        for si in storage_indices:
            assert si < db_index, "Storage delete happened after DB delete"


class TestDeleteCandidateNotFound:
    async def test_raises_when_candidate_not_found(self, svc, candidate_repo):
        candidate_repo.get_by_id.return_value = None
        with pytest.raises(CandidateNotFoundError):
            await svc.execute("nonexistent-cand")

    async def test_no_storage_delete_when_not_found(self, svc, candidate_repo, storage):
        candidate_repo.get_by_id.return_value = None
        with pytest.raises(CandidateNotFoundError):
            await svc.execute("nonexistent-cand")
        storage.delete.assert_not_called()


class TestDeleteCandidateStorageFailure:
    async def test_storage_failure_does_not_prevent_db_delete(self, svc, candidate_repo, storage):
        """Storage failures are non-fatal — DB record still gets deleted."""
        storage.delete.side_effect = Exception("Storage unavailable")
        await svc.execute("cand-001")  # should not raise
        candidate_repo.delete.assert_called_once_with("cand-001")


class TestDeleteCandidateStorageKeyDerivation:
    async def test_parsed_key_uses_stem_of_file_key(self, candidate_repo, storage):
        """Parsed key is derived from the stem of file_key (without extension)."""
        candidate_repo.get_by_id.return_value = _make_candidate(
            candidate_id="abc-123",
            file_key="cv/original/abc-123.docx",
        )
        svc = DeleteCandidateService(candidate_repo=candidate_repo, storage=storage)
        await svc.execute("abc-123")

        deleted_keys = [c.args[0] for c in storage.delete.call_args_list]
        assert "cv/original/abc-123.docx" in deleted_keys
        assert "cv/parsed/abc-123.txt" in deleted_keys
        assert "reports/abc-123.md" in deleted_keys