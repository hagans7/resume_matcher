
"""SubmitBatchService — validates and enqueues a batch CV evaluation job.

Steps:
  1. Validate job exists and is active
  2. Validate file count (1 ≤ n ≤ MAX_BATCH_SIZE)
  3. Deduplicate files within the batch by hash (HashSet O(n))
  4. Bulk DB deduplication: single IN query instead of N queries (O(1) roundtrip)
  5. Create batch DB record (status: queued)
  6. Create candidate records for each unique file (status: new)
  7. Store all files to storage
  8. Enqueue Celery process_batch task
  9. Return Batch entity

Import note: process_batch_task is imported as a MODULE (not as a function) so
tests can patch it via: patch("src.services.submit_batch.process_batch_task")
This avoids AttributeError when patching a name that was only available inside
a function's local scope via lazy import.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Import the module, not the function — required for test patchability.
# Accessing via module object (process_batch_task.process_batch.delay)
# means the name is resolvable at module level for unittest.mock.patch.
from src.tasks import process_batch_task

from src.core.constants.app_constants import (
    ALLOWED_FILE_EXTENSIONS,
    BATCH_STATUS_QUEUED,
    CANDIDATE_STATUS_NEW,
    HASH_ALGORITHM,
)
from src.core.exceptions.app_exceptions import (
    FileValidationError,
    FileTooLargeError,
    JobNotFoundError,
    ValidationError,
)
from src.core.logging.logger import get_logger
from src.entities.batch import Batch
from src.entities.candidate import Candidate
from src.interfaces.base_batch_repository import BaseBatchRepository
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_job_repository import BaseJobRepository
from src.interfaces.base_storage_client import BaseStorageClient

logger = get_logger(__name__)


class SubmitBatchService:

    def __init__(
        self,
        job_repo: BaseJobRepository,
        candidate_repo: BaseCandidateRepository,
        batch_repo: BaseBatchRepository,
        storage: BaseStorageClient,
        max_file_size_mb: int,
        max_batch_size: int,
    ) -> None:
        self._job_repo = job_repo
        self._candidate_repo = candidate_repo
        self._batch_repo = batch_repo
        self._storage = storage
        self._max_bytes = max_file_size_mb * 1024 * 1024
        self._max_batch_size = max_batch_size

    async def execute(
        self,
        job_id: str,
        files: list[tuple[str, bytes]],  # list of (filename, file_bytes)
    ) -> Batch:
        """Validate, store, and enqueue batch. Returns Batch entity with status=queued.

        Raises: JobNotFoundError, ValidationError, FileValidationError,
                FileTooLargeError, PersistenceError, StorageError.
        """
        # 1. Validate job
        job = await self._job_repo.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError(f"Job not found: {job_id}", {"job_id": job_id})
        if not job.is_active():
            raise ValidationError(
                f"Job {job_id!r} is not active.",
                {"job_id": job_id, "status": job.status},
            )

        # 2. Validate file count
        if len(files) == 0:
            raise ValidationError("Batch must contain at least one file.")
        if len(files) > self._max_batch_size:
            raise ValidationError(
                f"Batch size {len(files)} exceeds MAX_BATCH_SIZE={self._max_batch_size}.",
                {"submitted": len(files), "max": self._max_batch_size},
            )

        # 3a. Deduplicate within batch using HashSet — O(n), single pass
        seen_hashes: set[str] = set()
        unique_files: list[tuple[str, bytes, str]] = []  # (filename, bytes, hash)

        for filename, file_bytes in files:
            self._validate_file(file_bytes, filename)
            file_hash = hashlib.new(HASH_ALGORITHM, file_bytes).hexdigest()
            if file_hash not in seen_hashes:
                seen_hashes.add(file_hash)
                unique_files.append((filename, file_bytes, file_hash))

        intra_dupes = len(files) - len(unique_files)
        if intra_dupes > 0:
            logger.info(
                "batch_intra_duplicates_removed",
                job_id=job_id,
                removed=intra_dupes,
                unique=len(unique_files),
            )

        # 3b. Fix 3 — Bulk DB deduplication: single O(1) roundtrip instead of N queries.
        #     Find which hashes already exist for this job in one IN(...) query.
        all_hashes = [h for _, _, h in unique_files]
        existing_hashes = await self._candidate_repo.find_existing_hashes(job_id, all_hashes)
        if existing_hashes:
            before = len(unique_files)
            unique_files = [
                (fname, fbytes, fhash)
                for fname, fbytes, fhash in unique_files
                if fhash not in existing_hashes
            ]
            logger.info(
                "batch_db_duplicates_skipped",
                job_id=job_id,
                skipped=before - len(unique_files),
                remaining=len(unique_files),
            )

        if len(unique_files) == 0:
            from src.core.exceptions.app_exceptions import ValidationError as _VE
            raise _VE(
                "All submitted files are duplicates of previously evaluated CVs for this job.",
                {"job_id": job_id},
            )

        # 4. Create batch record
        batch_id = str(uuid.uuid4())
        batch = Batch(
            id=batch_id,
            job_id=job_id,
            total=len(unique_files),
            status=BATCH_STATUS_QUEUED,
            created_at=datetime.now(timezone.utc),
        )
        created_batch = await self._batch_repo.create(batch)

        # 5 & 6. Create candidate records and store files
        for filename, file_bytes, file_hash in unique_files:
            candidate_id = str(uuid.uuid4())
            ext = Path(filename).suffix.lower()
            file_key = f"cv/original/{candidate_id}{ext}"

            await self._storage.save(
                key=file_key,
                data=file_bytes,
                content_type="application/octet-stream",
            )

            candidate = Candidate(
                id=candidate_id,
                job_id=job_id,
                file_key=file_key,
                file_hash=file_hash,
                original_filename=filename,
                status=CANDIDATE_STATUS_NEW,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                batch_id=batch_id,
            )
            await self._candidate_repo.create(candidate)

        # 8. Enqueue Celery task — accessed via module object (not local import)
        # This pattern allows tests to patch: patch("src.services.submit_batch.process_batch_task")
        process_batch_task.process_batch.delay(batch_id)

        logger.info(
            "batch_submitted",
            batch_id=batch_id,
            job_id=job_id,
            total=len(unique_files),
        )
        return created_batch

    def _validate_file(self, file_bytes: bytes, filename: str) -> None:
        if len(file_bytes) == 0:
            raise FileValidationError("File is empty.", {"filename": filename})
        if len(file_bytes) > self._max_bytes:
            raise FileTooLargeError(
                f"File exceeds size limit.",
                {"filename": filename, "size_bytes": len(file_bytes)},
            )
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_FILE_EXTENSIONS:
            raise FileValidationError(
                f"File type {ext!r} not allowed.",
                {"filename": filename},
            )