"""Service providers — wires service dependencies via FastAPI Depends chain."""

from fastapi import Depends

from src.core.config.settings import settings
from src.interfaces.base_batch_repository import BaseBatchRepository
from src.interfaces.base_cache_client import BaseCacheClient
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_document_extractor import BaseDocumentExtractor
from src.interfaces.base_job_repository import BaseJobRepository
from src.interfaces.base_resume_matcher import BaseResumeMatcher
from src.interfaces.base_storage_client import BaseStorageClient
from src.providers.infrastructure import (
    get_cache_client,
    get_document_extractor,
    get_resume_matcher,
    get_storage_client,
)
from src.providers.repositories import get_batch_repo, get_candidate_repo, get_job_repo
from src.services.check_batch_status import CheckBatchStatusService
from src.services.create_job import CreateJobService
from src.services.evaluate_resume import EvaluateResumeService
from src.services.ingest_candidate import IngestCandidateService
from src.services.list_candidates import ListCandidatesService
from src.services.mask_pii import MaskPIIService
from src.services.prepare_cv_text import PrepareCVTextService
from src.services.cancel_batch import CancelBatchService
from src.services.delete_candidate import DeleteCandidateService
from src.services.review_candidate import ReviewCandidateService
from src.services.submit_batch import SubmitBatchService


def get_mask_pii_service() -> MaskPIIService:
    return MaskPIIService()


def get_ingest_candidate_service(
    candidate_repo: BaseCandidateRepository = Depends(get_candidate_repo),
    job_repo: BaseJobRepository = Depends(get_job_repo),
    storage: BaseStorageClient = Depends(get_storage_client),
) -> IngestCandidateService:
    return IngestCandidateService(
        candidate_repo=candidate_repo,
        job_repo=job_repo,
        storage=storage,
        max_file_size_mb=settings.max_file_size_mb,
    )


def get_prepare_cv_text_service(
    extractor: BaseDocumentExtractor = Depends(get_document_extractor),
    storage: BaseStorageClient = Depends(get_storage_client),
) -> PrepareCVTextService:
    return PrepareCVTextService(
        extractor=extractor,
        storage=storage,
        pii_masker=MaskPIIService(),
    )


def get_create_job_service(
    job_repo: BaseJobRepository = Depends(get_job_repo),
) -> CreateJobService:
    return CreateJobService(job_repo=job_repo)


def get_evaluate_resume_service(
    ingest: IngestCandidateService = Depends(get_ingest_candidate_service),
    prepare: PrepareCVTextService = Depends(get_prepare_cv_text_service),
    candidate_repo: BaseCandidateRepository = Depends(get_candidate_repo),
    job_repo: BaseJobRepository = Depends(get_job_repo),
    matcher: BaseResumeMatcher = Depends(get_resume_matcher),
    cache: BaseCacheClient = Depends(get_cache_client),
    storage: BaseStorageClient = Depends(get_storage_client),
) -> EvaluateResumeService:
    return EvaluateResumeService(
        ingest_service=ingest,
        prepare_service=prepare,
        candidate_repo=candidate_repo,
        job_repo=job_repo,
        matcher=matcher,
        cache=cache,
        storage=storage,
    )


def get_submit_batch_service(
    job_repo: BaseJobRepository = Depends(get_job_repo),
    candidate_repo: BaseCandidateRepository = Depends(get_candidate_repo),
    batch_repo: BaseBatchRepository = Depends(get_batch_repo),
    storage: BaseStorageClient = Depends(get_storage_client),
) -> SubmitBatchService:
    return SubmitBatchService(
        job_repo=job_repo,
        candidate_repo=candidate_repo,
        batch_repo=batch_repo,
        storage=storage,
        max_file_size_mb=settings.max_file_size_mb,
        max_batch_size=settings.max_batch_size,
    )


def get_check_batch_status_service(
    batch_repo: BaseBatchRepository = Depends(get_batch_repo),
    candidate_repo: BaseCandidateRepository = Depends(get_candidate_repo),
) -> CheckBatchStatusService:
    return CheckBatchStatusService(
        batch_repo=batch_repo,
        candidate_repo=candidate_repo,
    )


def get_list_candidates_service(
    job_repo: BaseJobRepository = Depends(get_job_repo),
    candidate_repo: BaseCandidateRepository = Depends(get_candidate_repo),
) -> ListCandidatesService:
    return ListCandidatesService(
        job_repo=job_repo,
        candidate_repo=candidate_repo,
    )


def get_review_candidate_service(
    candidate_repo: BaseCandidateRepository = Depends(get_candidate_repo),
) -> ReviewCandidateService:
    return ReviewCandidateService(candidate_repo=candidate_repo)


def get_delete_candidate_service(
    candidate_repo: BaseCandidateRepository = Depends(get_candidate_repo),
    storage: BaseStorageClient = Depends(get_storage_client),
) -> DeleteCandidateService:
    return DeleteCandidateService(candidate_repo=candidate_repo, storage=storage)
 
 
def get_cancel_batch_service(
    batch_repo: BaseBatchRepository = Depends(get_batch_repo),
) -> CancelBatchService:
    return CancelBatchService(batch_repo=batch_repo)