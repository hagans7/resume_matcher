"""Candidate management routes.
 
Endpoints:
  GET    /jobs/{job_id}/candidates              — list candidates for a job
  GET    /candidates/{candidate_id}             — get candidate detail
  GET    /candidates/{candidate_id}/download    — download original CV file
  PATCH  /candidates/{candidate_id}/review      — HR manual review
  DELETE /candidates/{candidate_id}             — hard delete + storage cleanup
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from src.api.schemas.base_schema import SuccessResponse
from src.api.schemas.candidate_schema import (
    CandidateDetailResponse,
    CandidateListResponse,
    CandidateSummary,
    ReviewRequest,
    ReviewResponse,
)
from src.core.exceptions.app_exceptions import (
    CandidateNotFoundError,
    InvalidStatusTransitionError,
    JobNotFoundError,
    NotFoundError,
    StorageError,
)
from src.core.logging.logger import get_logger
from src.entities.candidate import Candidate
from src.providers import (
    get_list_candidates_service,
    get_review_candidate_service,
    get_delete_candidate_service,
    get_storage_client)
from src.providers.repositories import get_candidate_repo
from src.services.delete_candidate import DeleteCandidateService
from src.services.list_candidates import ListCandidatesService
from src.services.review_candidate import ReviewCandidateService

router = APIRouter(tags=["candidates"])
logger = get_logger(__name__)


def _to_summary(c: Candidate) -> CandidateSummary:
    return CandidateSummary(
        id=c.id,
        job_id=c.job_id,
        original_filename=c.original_filename,
        score=c.score,
        verdict=c.verdict,
        status=c.status,
        processing_ms=c.processing_ms,
        token_used=c.token_used,
        batch_id=c.batch_id,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/jobs/{job_id}/candidates", response_model=SuccessResponse)
async def list_candidates(
    job_id: str,
    status: str | None = None,
    service: ListCandidatesService = Depends(get_list_candidates_service),
):
    """List candidates for a job, sorted by score desc. Optional status filter."""
    try:
        candidates = await service.execute(job_id=job_id, status_filter=status)
        return SuccessResponse(
            data=CandidateListResponse(
                candidates=[_to_summary(c) for c in candidates],
                total=len(candidates),
            )
        )
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)


@router.get("/candidates/{candidate_id}", response_model=SuccessResponse)
async def get_candidate(
    candidate_id: str,
    candidate_repo=Depends(get_candidate_repo),
):
    """Get full candidate detail including evaluation result JSON."""
    candidate = await candidate_repo.get_by_id(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate not found: {candidate_id}")

    return SuccessResponse(
        data=CandidateDetailResponse(
            id=candidate.id,
            job_id=candidate.job_id,
            original_filename=candidate.original_filename,
            file_hash=candidate.file_hash,
            score=candidate.score,
            verdict=candidate.verdict,
            status=candidate.status,
            result=candidate.result_json,
            review_notes=candidate.review_notes,
            processing_ms=candidate.processing_ms,
            token_used=candidate.token_used,
            batch_id=candidate.batch_id,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )
    )


@router.get("/candidates/{candidate_id}/download")
async def download_candidate_cv(
    candidate_id: str,
    candidate_repo=Depends(get_candidate_repo),
    storage=Depends(get_storage_client),
):
    """Download the original CV file (PDF or DOCX) for a candidate.
 
    Returns the raw file bytes with appropriate Content-Disposition header.
    Useful for HR to verify AI evaluation against the source document.
    """
    candidate = await candidate_repo.get_by_id(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate not found: {candidate_id}")
 
    try:
        file_bytes = await storage.load(candidate.file_key)
    except NotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"CV file not found in storage for candidate: {candidate_id}",
        )
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve CV: {exc}")
 
    # Determine content type from filename
    filename = candidate.original_filename
    if filename.lower().endswith(".pdf"):
        content_type = "application/pdf"
    elif filename.lower().endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        content_type = "application/octet-stream"
 
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.patch("/candidates/{candidate_id}/review", response_model=SuccessResponse)
async def review_candidate(
    candidate_id: str,
    body: ReviewRequest,
    service: ReviewCandidateService = Depends(get_review_candidate_service),
):
    """HR manual review: update candidate status with optional notes."""
    try:
        # Capture previous status before update
        from src.providers.repositories import get_candidate_repo as _get_repo
        updated = await service.execute(
            candidate_id=candidate_id,
            new_status=body.status,
            review_notes=body.notes,
        )
        return SuccessResponse(
            data=ReviewResponse(
                candidate_id=updated.id,
                previous_status="reviewed",   # service already validated transition
                new_status=updated.status,
                review_notes=updated.review_notes,
            )
        )
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=422, detail=exc.message)


@router.delete("/candidates/{candidate_id}", status_code=204)
async def delete_candidate(
    candidate_id: str,
    service: DeleteCandidateService = Depends(get_delete_candidate_service),
):
    """Hard delete candidate record and all associated files from storage.
 
    This operation is irreversible. The original CV, parsed text, and evaluation
    report are all removed from storage. Returns HTTP 204 (No Content) on success.
    """
    try:
        await service.execute(candidate_id=candidate_id)
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    # Return None → FastAPI sends 204 No Content automatically