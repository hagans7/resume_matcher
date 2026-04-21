"""Interfaces package. Re-exports all ABCs."""

from src.interfaces.base_batch_repository import BaseBatchRepository
from src.interfaces.base_cache_client import BaseCacheClient
from src.interfaces.base_candidate_repository import BaseCandidateRepository
from src.interfaces.base_document_extractor import BaseDocumentExtractor
from src.interfaces.base_job_repository import BaseJobRepository
from src.interfaces.base_resume_matcher import BaseResumeMatcher
from src.interfaces.base_storage_client import BaseStorageClient
from src.interfaces.base_tracer_client import BaseTracerClient

__all__ = [
    "BaseBatchRepository",
    "BaseCacheClient",
    "BaseCandidateRepository",
    "BaseDocumentExtractor",
    "BaseJobRepository",
    "BaseResumeMatcher",
    "BaseStorageClient",
    "BaseTracerClient",
]
