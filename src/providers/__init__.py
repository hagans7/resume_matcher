"""Providers package — single import entry point for routes.

Routes import ONLY from here. Never import from infrastructure/repositories/services directly.
"""

from src.providers.infrastructure import (
    get_cache_client,
    get_db_session,
    get_document_extractor,
    get_resume_matcher,
    get_storage_client,
    get_tracer_client,
)
from src.providers.repositories import get_batch_repo, get_candidate_repo, get_job_repo
from src.providers.services import (
    get_check_batch_status_service,
    get_create_job_service,
    get_evaluate_resume_service,
    get_list_candidates_service,
    get_mask_pii_service,
    get_review_candidate_service,
    get_submit_batch_service,
)

__all__ = [
    # Infrastructure
    "get_cache_client",
    "get_db_session",
    "get_document_extractor",
    "get_resume_matcher",
    "get_storage_client",
    "get_tracer_client",
    # Repositories
    "get_batch_repo",
    "get_candidate_repo",
    "get_job_repo",
    # Services
    "get_check_batch_status_service",
    "get_create_job_service",
    "get_evaluate_resume_service",
    "get_list_candidates_service",
    "get_mask_pii_service",
    "get_review_candidate_service",
    "get_submit_batch_service",
]
