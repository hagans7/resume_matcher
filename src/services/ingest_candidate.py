"""IngestCandidateService — validates, deduplicates, stores, and creates a candidate record.

Extracted from original god-service evaluate_resume.py per blueprint v2 revision.
Single responsibility: file intake only. No extraction, no evaluation.

Steps:
  1. Validate file size + extension
  2. Compute SHA-256 hash (O(n), streaming)
  3. Check duplicate via composite DB index (O(log n))
  4. Verify job exists and is active
  5. Store raw file to storage
  6. Create candidate DB record (status: processing)
  7. Return Candidate entity
"""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.core.constants.app_constants import (
    ALLOWED_FILE_EXTENSIONS,
    CANDIDATE_STATUS_PROCESSING,
    HASH_ALGORITHM,
)
from src.core.exceptions.app_exceptions import (
    DuplicateCVError,
    FileTooLargeError,
    FileValidationError,
    JobNotFoundError,
    ValidationError,
)
from src.core.logging.logger import get_logger
from src.entities.candidate import Candidate
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_job_repository import BaseJobRepository
from src.interfaces.base_storage_client import BaseStorageClient

logger = get_logger(__name__)


class IngestCandidateService:

    def __init__(
        self,
        candidate_repo: BaseCandidateRepository,
        job_repo: BaseJobRepository,
        storage: BaseStorageClient,
        max_file_size_mb: int,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._job_repo = job_repo
        self._storage = storage
        self._max_bytes = max_file_size_mb * 1024 * 1024

    async def execute(
        self,
        job_id: str,
        file_bytes: bytes,
        filename: str,
        batch_id: str | None = None,
    ) -> Candidate:
        """Validate, deduplicate, store CV and create DB record.

        Raises: FileValidationError, FileTooLargeError, DuplicateCVError,
                JobNotFoundError, ValidationError, PersistenceError, StorageError.
        """
        # 1. Validate file
        self._validate_file(file_bytes, filename)

        # 2. Compute SHA-256 hash — O(n) streaming
        file_hash = self._compute_hash(file_bytes)

        # 3. Check for duplicate CV for this job
        existing = await self._candidate_repo.find_by_hash(job_id, file_hash)
        if existing is not None:
            raise DuplicateCVError(
                f"CV already submitted for this job: {filename}",
                {"job_id": job_id, "file_hash": file_hash, "existing_id": existing.id},
            )

        # 4. Verify job exists and is accepting submissions
        job = await self._job_repo.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError(f"Job not found: {job_id}", {"job_id": job_id})
        if not job.is_active():
            raise ValidationError(
                f"Job {job_id!r} is not active (status={job.status!r}).",
                {"job_id": job_id, "status": job.status},
            )

        # 5. Generate candidate ID and store file
        candidate_id = str(uuid.uuid4())
        ext = Path(filename).suffix.lower()
        file_key = f"cv/original/{candidate_id}{ext}"

        await self._storage.save(
            key=file_key,
            data=file_bytes,
            content_type="application/octet-stream",
        )

        # 6. Create candidate record
        candidate = Candidate(
            id=candidate_id,
            job_id=job_id,
            file_key=file_key,
            file_hash=file_hash,
            original_filename=filename,
            status=CANDIDATE_STATUS_PROCESSING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            batch_id=batch_id,
        )

        created = await self._candidate_repo.create(candidate)

        logger.info(
            "candidate_ingested",
            candidate_id=created.id,
            job_id=job_id,
            filename=filename,
            file_hash=file_hash[:12] + "...",
            batch_id=batch_id,
        )
        return created

    def _validate_file(self, file_bytes: bytes, filename: str) -> None:
        """Validate size and extension. Raises FileTooLargeError, FileValidationError."""
        if len(file_bytes) == 0:
            raise FileValidationError("Uploaded file is empty.", {"filename": filename})

        if len(file_bytes) > self._max_bytes:
            raise FileTooLargeError(
                f"File exceeds {self._max_bytes // (1024 * 1024)}MB limit.",
                {"filename": filename, "size_bytes": len(file_bytes)},
            )

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_FILE_EXTENSIONS:
            raise FileValidationError(
                f"File type {ext!r} is not allowed. Accepted: {sorted(ALLOWED_FILE_EXTENSIONS)}",
                {"filename": filename},
            )

    @staticmethod
    def _compute_hash(file_bytes: bytes) -> str:
        """Compute SHA-256 hex digest. O(n) time, O(1) memory."""
        return hashlib.new(HASH_ALGORITHM, file_bytes).hexdigest()
