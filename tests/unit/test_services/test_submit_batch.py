# """Unit tests for SubmitBatchService — bulk deduplication and validation."""

# from datetime import datetime, timezone
# from unittest.mock import AsyncMock, patch

# import pytest

# from src.core.exceptions.app_exceptions import (
#     FileTooLargeError,
#     FileValidationError,
#     JobNotFoundError,
#     ValidationError,
# )
# from src.entities.batch import Batch
# from src.entities.candidate import Candidate
# from src.entities.job_requirement import JobRequirement
# from src.services.submit_batch import SubmitBatchService


# def _make_job(status="active") -> JobRequirement:
#     return JobRequirement(
#         id="job-001",
#         title="Dev",
#         description="Python developer",
#         evaluation_mode="standard",
#         status=status,
#         created_at=datetime.now(timezone.utc),
#     )


# def _make_batch() -> Batch:
#     return Batch(
#         id="batch-001",
#         job_id="job-001",
#         total=2,
#         status="queued",
#         created_at=datetime.now(timezone.utc),
#     )


# def _make_candidate(fhash: str) -> Candidate:
#     return Candidate(
#         id="c-001",
#         job_id="job-001",
#         file_key="cv/original/c-001.pdf",
#         file_hash=fhash,
#         original_filename="cv.pdf",
#         status="new",
#         created_at=datetime.now(timezone.utc),
#         updated_at=datetime.now(timezone.utc),
#     )


# @pytest.fixture
# def job_repo():
#     repo = AsyncMock()
#     repo.get_by_id.return_value = _make_job()
#     return repo


# @pytest.fixture
# def candidate_repo():
#     repo = AsyncMock()
#     repo.find_existing_hashes.return_value = set()  # no DB dupes by default
#     repo.create.return_value = _make_candidate("abc")
#     return repo


# @pytest.fixture
# def batch_repo():
#     repo = AsyncMock()
#     repo.create.return_value = _make_batch()
#     return repo


# @pytest.fixture
# def storage():
#     s = AsyncMock()
#     s.save.return_value = "cv/original/x.pdf"
#     return s


# @pytest.fixture
# def svc(job_repo, candidate_repo, batch_repo, storage):
#     return SubmitBatchService(
#         job_repo=job_repo,
#         candidate_repo=candidate_repo,
#         batch_repo=batch_repo,
#         storage=storage,
#         max_file_size_mb=10,
#         max_batch_size=200,
#     )


# PDF = b"%PDF-1.4 " + b"x" * 200
# PDF2 = b"%PDF-1.4 " + b"y" * 200  # different content → different hash


# class TestIntraBatchDeduplication:
#     """Intra-batch dedup uses HashSet — duplicates within submitted files are removed."""

#     async def test_duplicate_files_in_batch_are_deduplicated(self, svc, batch_repo):
#         # Submit same file twice — should result in total=1
#         with patch("src.services.submit_batch.process_batch") as mock_task:
#             mock_task.delay = AsyncMock()
#             await svc.execute("job-001", [("cv.pdf", PDF), ("cv_copy.pdf", PDF)])
#         # Only 1 unique file should be created
#         batch_repo.create.assert_called_once()
#         created_batch_arg = batch_repo.create.call_args[0][0]
#         assert created_batch_arg.total == 1

#     async def test_unique_files_all_kept(self, svc, batch_repo):
#         with patch("src.services.submit_batch.process_batch") as mock_task:
#             mock_task.delay = AsyncMock()
#             await svc.execute("job-001", [("cv1.pdf", PDF), ("cv2.pdf", PDF2)])
#         created_batch_arg = batch_repo.create.call_args[0][0]
#         assert created_batch_arg.total == 2


# class TestDBBulkDeduplication:
#     """Fix 3: bulk IN query, not per-file queries."""

#     async def test_uses_bulk_find_existing_hashes(self, svc, candidate_repo):
#         with patch("src.services.submit_batch.process_batch") as mock_task:
#             mock_task.delay = AsyncMock()
#             await svc.execute("job-001", [("cv1.pdf", PDF), ("cv2.pdf", PDF2)])
#         # Must be called ONCE with both hashes — not twice with individual hashes
#         candidate_repo.find_existing_hashes.assert_called_once()
#         call_args = candidate_repo.find_existing_hashes.call_args
#         hashes_arg = call_args[0][1] if call_args[0] else call_args[1].get("file_hashes", [])
#         assert len(hashes_arg) == 2

#     async def test_skips_files_already_in_db(self, svc, candidate_repo, batch_repo):
#         import hashlib
#         existing_hash = hashlib.sha256(PDF).hexdigest()
#         candidate_repo.find_existing_hashes.return_value = {existing_hash}

#         with patch("src.services.submit_batch.process_batch") as mock_task:
#             mock_task.delay = AsyncMock()
#             await svc.execute("job-001", [("existing.pdf", PDF), ("new.pdf", PDF2)])

#         # Only PDF2 should be created (PDF already exists in DB)
#         created_batch_arg = batch_repo.create.call_args[0][0]
#         assert created_batch_arg.total == 1

#     async def test_all_duplicates_raises_validation_error(self, svc, candidate_repo):
#         import hashlib
#         existing_hash = hashlib.sha256(PDF).hexdigest()
#         candidate_repo.find_existing_hashes.return_value = {existing_hash}

#         with pytest.raises(ValidationError, match="duplicates"):
#             await svc.execute("job-001", [("existing.pdf", PDF)])


# class TestBatchSizeLimits:
#     async def test_empty_batch_raises(self, svc):
#         with pytest.raises(ValidationError, match="at least one"):
#             await svc.execute("job-001", [])

#     async def test_exceeds_max_batch_size_raises(self, svc):
#         files = [("cv.pdf", PDF)] * 201
#         with pytest.raises(ValidationError, match="MAX_BATCH_SIZE"):
#             await svc.execute("job-001", files)


# class TestJobValidation:
#     async def test_missing_job_raises(self, svc, job_repo):
#         job_repo.get_by_id.return_value = None
#         with pytest.raises(JobNotFoundError):
#             await svc.execute("nonexistent", [("cv.pdf", PDF)])

#     async def test_archived_job_raises(self, svc, job_repo):
#         job_repo.get_by_id.return_value = _make_job(status="archived")
#         with pytest.raises(ValidationError, match="not active"):
#             await svc.execute("job-001", [("cv.pdf", PDF)])

"""Unit tests for SubmitBatchService — bulk deduplication and validation."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions.app_exceptions import (
    FileTooLargeError,
    FileValidationError,
    JobNotFoundError,
    ValidationError,
)
from src.entities.batch import Batch
from src.entities.candidate import Candidate
from src.entities.job_requirement import JobRequirement
from src.services.submit_batch import SubmitBatchService


def _make_job(status="active") -> JobRequirement:
    return JobRequirement(
        id="job-001",
        title="Dev",
        description="Python developer",
        evaluation_mode="standard",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def _make_batch() -> Batch:
    return Batch(
        id="batch-001",
        job_id="job-001",
        total=2,
        status="queued",
        created_at=datetime.now(timezone.utc),
    )


def _make_candidate(fhash: str) -> Candidate:
    return Candidate(
        id="c-001",
        job_id="job-001",
        file_key="cv/original/c-001.pdf",
        file_hash=fhash,
        original_filename="cv.pdf",
        status="new",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def job_repo():
    repo = AsyncMock()
    repo.get_by_id.return_value = _make_job()
    return repo


@pytest.fixture
def candidate_repo():
    repo = AsyncMock()
    repo.find_existing_hashes.return_value = set()  # no DB dupes by default
    repo.create.return_value = _make_candidate("abc")
    return repo


@pytest.fixture
def batch_repo():
    repo = AsyncMock()
    repo.create.return_value = _make_batch()
    return repo


@pytest.fixture
def storage():
    s = AsyncMock()
    s.save.return_value = "cv/original/x.pdf"
    return s


@pytest.fixture
def svc(job_repo, candidate_repo, batch_repo, storage):
    return SubmitBatchService(
        job_repo=job_repo,
        candidate_repo=candidate_repo,
        batch_repo=batch_repo,
        storage=storage,
        max_file_size_mb=10,
        max_batch_size=200,
    )


PDF = b"%PDF-1.4 " + b"x" * 200
PDF2 = b"%PDF-1.4 " + b"y" * 200  # different content → different hash

# Correct patch path: target the MODULE attribute, not a non-existent function attribute.
# submit_batch.py imports process_batch_task as a module, then calls
# process_batch_task.process_batch.delay(). So we patch the module's process_batch attr.
PATCH_TARGET = "src.services.submit_batch.process_batch_task"


class TestIntraBatchDeduplication:
    """Intra-batch dedup uses HashSet — duplicates within submitted files are removed."""

    async def test_duplicate_files_in_batch_are_deduplicated(self, svc, batch_repo):
        # Submit same file twice — should result in total=1
        with patch(PATCH_TARGET) as mock_module:
            mock_module.process_batch = MagicMock()
            mock_module.process_batch.delay = MagicMock()
            await svc.execute("job-001", [("cv.pdf", PDF), ("cv_copy.pdf", PDF)])
        # Only 1 unique file should be created
        batch_repo.create.assert_called_once()
        created_batch_arg = batch_repo.create.call_args[0][0]
        assert created_batch_arg.total == 1

    async def test_unique_files_all_kept(self, svc, batch_repo):
        with patch(PATCH_TARGET) as mock_module:
            mock_module.process_batch = MagicMock()
            mock_module.process_batch.delay = MagicMock()
            await svc.execute("job-001", [("cv1.pdf", PDF), ("cv2.pdf", PDF2)])
        created_batch_arg = batch_repo.create.call_args[0][0]
        assert created_batch_arg.total == 2


class TestDBBulkDeduplication:
    """Fix 3: bulk IN query, not per-file queries."""

    async def test_uses_bulk_find_existing_hashes(self, svc, candidate_repo):
        with patch(PATCH_TARGET) as mock_module:
            mock_module.process_batch = MagicMock()
            mock_module.process_batch.delay = MagicMock()
            await svc.execute("job-001", [("cv1.pdf", PDF), ("cv2.pdf", PDF2)])
        # Must be called ONCE with both hashes — not N individual queries
        candidate_repo.find_existing_hashes.assert_called_once()
        call_args = candidate_repo.find_existing_hashes.call_args
        hashes_arg = call_args[0][1] if call_args[0] else call_args[1].get("file_hashes", [])
        assert len(hashes_arg) == 2

    async def test_skips_files_already_in_db(self, svc, candidate_repo, batch_repo):
        import hashlib
        existing_hash = hashlib.sha256(PDF).hexdigest()
        candidate_repo.find_existing_hashes.return_value = {existing_hash}

        with patch(PATCH_TARGET) as mock_module:
            mock_module.process_batch = MagicMock()
            mock_module.process_batch.delay = MagicMock()
            await svc.execute("job-001", [("existing.pdf", PDF), ("new.pdf", PDF2)])

        # Only PDF2 should be created (PDF already exists in DB)
        created_batch_arg = batch_repo.create.call_args[0][0]
        assert created_batch_arg.total == 1

    async def test_all_duplicates_raises_validation_error(self, svc, candidate_repo):
        import hashlib
        existing_hash = hashlib.sha256(PDF).hexdigest()
        candidate_repo.find_existing_hashes.return_value = {existing_hash}

        with pytest.raises(ValidationError, match="duplicates"):
            await svc.execute("job-001", [("existing.pdf", PDF)])


class TestBatchSizeLimits:
    async def test_empty_batch_raises(self, svc):
        with pytest.raises(ValidationError, match="at least one"):
            await svc.execute("job-001", [])

    async def test_exceeds_max_batch_size_raises(self, svc):
        files = [("cv.pdf", PDF)] * 201
        with pytest.raises(ValidationError, match="MAX_BATCH_SIZE"):
            await svc.execute("job-001", files)


class TestJobValidation:
    async def test_missing_job_raises(self, svc, job_repo):
        job_repo.get_by_id.return_value = None
        with pytest.raises(JobNotFoundError):
            await svc.execute("nonexistent", [("cv.pdf", PDF)])

    async def test_archived_job_raises(self, svc, job_repo):
        job_repo.get_by_id.return_value = _make_job(status="archived")
        with pytest.raises(ValidationError, match="not active"):
            await svc.execute("job-001", [("cv.pdf", PDF)])