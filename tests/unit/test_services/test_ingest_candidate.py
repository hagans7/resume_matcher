"""Unit tests for IngestCandidateService."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.core.exceptions.app_exceptions import (
    DuplicateCVError,
    FileValidationError,
    FileTooLargeError,
    JobNotFoundError,
    ValidationError,
)
from src.entities.job_requirement import JobRequirement
from src.services.ingest_candidate import IngestCandidateService


def _make_job(status="active") -> JobRequirement:
    return JobRequirement(
        id="job-001",
        title="Dev",
        description="Python developer",
        evaluation_mode="standard",
        status=status,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def candidate_repo():
    return AsyncMock()


@pytest.fixture
def job_repo():
    repo = AsyncMock()
    repo.get_by_id.return_value = _make_job()
    return repo


@pytest.fixture
def storage():
    mock = AsyncMock()
    mock.save.return_value = "cv/original/test.pdf"
    return mock


@pytest.fixture
def svc(candidate_repo, job_repo, storage):
    return IngestCandidateService(
        candidate_repo=candidate_repo,
        job_repo=job_repo,
        storage=storage,
        max_file_size_mb=10,
    )


@pytest.fixture
def valid_pdf() -> bytes:
    return b"%PDF-1.4 " + b"x" * 100


class TestValidIngestion:
    async def test_creates_candidate_on_valid_input(self, svc, candidate_repo, valid_pdf):
        from src.entities.candidate import Candidate
        created = Candidate(
            id="new-id",
            job_id="job-001",
            file_key="cv/original/new-id.pdf",
            file_hash="abc",
            original_filename="cv.pdf",
            status="processing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        candidate_repo.find_by_hash.return_value = None
        candidate_repo.create.return_value = created

        result = await svc.execute("job-001", valid_pdf, "cv.pdf")
        assert result.id == "new-id"
        assert result.status == "processing"
        candidate_repo.create.assert_called_once()

    async def test_stores_file_to_storage(self, svc, candidate_repo, storage, valid_pdf):
        from src.entities.candidate import Candidate
        candidate_repo.find_by_hash.return_value = None
        candidate_repo.create.return_value = Candidate(
            id="x", job_id="job-001", file_key="k", file_hash="h",
            original_filename="cv.pdf", status="processing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        await svc.execute("job-001", valid_pdf, "cv.pdf")
        storage.save.assert_called_once()


class TestFileValidation:
    async def test_rejects_empty_file(self, svc):
        with pytest.raises(FileValidationError, match="empty"):
            await svc.execute("job-001", b"", "cv.pdf")

    async def test_rejects_file_too_large(self, svc):
        big = b"x" * (11 * 1024 * 1024)  # 11MB
        with pytest.raises(FileTooLargeError):
            await svc.execute("job-001", big, "cv.pdf")

    async def test_rejects_invalid_extension(self, svc, valid_pdf):
        with pytest.raises(FileValidationError, match="not allowed"):
            await svc.execute("job-001", valid_pdf, "cv.exe")

    async def test_accepts_pdf(self, svc, candidate_repo, valid_pdf):
        from src.entities.candidate import Candidate
        candidate_repo.find_by_hash.return_value = None
        candidate_repo.create.return_value = Candidate(
            id="x", job_id="job-001", file_key="k", file_hash="h",
            original_filename="cv.pdf", status="processing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        result = await svc.execute("job-001", valid_pdf, "resume.pdf")
        assert result is not None

    async def test_accepts_docx(self, svc, candidate_repo):
        from src.entities.candidate import Candidate
        docx = b"PK\x03\x04" + b"x" * 100  # minimal zip signature (docx is zip)
        candidate_repo.find_by_hash.return_value = None
        candidate_repo.create.return_value = Candidate(
            id="x", job_id="job-001", file_key="k", file_hash="h",
            original_filename="cv.docx", status="processing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        result = await svc.execute("job-001", docx, "resume.docx")
        assert result is not None


class TestDuplication:
    async def test_raises_on_duplicate_hash(self, svc, candidate_repo, valid_pdf):
        from src.entities.candidate import Candidate
        existing = Candidate(
            id="old-id", job_id="job-001", file_key="k", file_hash="h",
            original_filename="cv.pdf", status="evaluated",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        candidate_repo.find_by_hash.return_value = existing
        with pytest.raises(DuplicateCVError):
            await svc.execute("job-001", valid_pdf, "cv.pdf")


class TestJobValidation:
    async def test_raises_when_job_not_found(self, svc, candidate_repo, job_repo, valid_pdf):
        candidate_repo.find_by_hash.return_value = None
        job_repo.get_by_id.return_value = None
        with pytest.raises(JobNotFoundError):
            await svc.execute("nonexistent-job", valid_pdf, "cv.pdf")

    async def test_raises_when_job_archived(self, svc, candidate_repo, job_repo, valid_pdf):
        candidate_repo.find_by_hash.return_value = None
        job_repo.get_by_id.return_value = _make_job(status="archived")
        with pytest.raises(ValidationError, match="not active"):
            await svc.execute("job-001", valid_pdf, "cv.pdf")
