"""Job management routes.
 
Endpoints:
  POST   /jobs                  — create new job
  GET    /jobs                  — list active jobs
  GET    /jobs/{job_id}         — get job detail
  PUT    /jobs/{job_id}         — update title/description
  PATCH  /jobs/{job_id}/archive — soft-delete (status → archived)
"""
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas.base_schema import SuccessResponse
from src.api.schemas.job_schema import CreateJobRequest, JobResponse, UpdateJobRequest
from src.core.constants.app_constants import JOB_STATUS_ARCHIVED
from src.core.exceptions.app_exceptions import JobNotFoundError, ValidationError
from src.core.logging.logger import get_logger
from src.entities.job_requirement import JobRequirement
from src.providers import get_create_job_service
from src.providers.repositories import get_job_repo
from src.services.create_job import CreateJobService

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)


def _to_response(job: JobRequirement) -> JobResponse:
    return JobResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        evaluation_mode=job.evaluation_mode,
        status=job.status,
        created_at=job.created_at,
        created_by=job.created_by,
    )


@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    service: CreateJobService = Depends(get_create_job_service),
):
    """Create a new job requirement. Returns job with generated ID."""
    try:
        job = await service.execute(
            title=body.title,
            description=body.description,
            evaluation_mode=body.evaluation_mode,
        )
        return SuccessResponse(data=_to_response(job))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message)


@router.get("", response_model=SuccessResponse)
async def list_jobs(
    job_repo=Depends(get_job_repo),
):
    """List all active job requirements ordered by created_at desc."""
    jobs = await job_repo.list_active()
    return SuccessResponse(data=[_to_response(j) for j in jobs])


@router.get("/{job_id}", response_model=SuccessResponse)
async def get_job(
    job_id: str,
    job_repo=Depends(get_job_repo),
):
    """Get a specific job by ID."""
    from src.core.exceptions.app_exceptions import JobNotFoundError
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return SuccessResponse(data=_to_response(job))


@router.put("/{job_id}", response_model=SuccessResponse)
async def update_job(
    job_id: str,
    body: UpdateJobRequest,
    job_repo=Depends(get_job_repo),
):
    """Update job title and description. Job must be active."""
    try:
        updated = await job_repo.update(
            job_id=job_id,
            title=body.title,
            description=body.description,
        )
        return SuccessResponse(data=_to_response(updated))
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
 
 
@router.patch("/{job_id}/archive", response_model=SuccessResponse)
async def archive_job(
    job_id: str,
    job_repo=Depends(get_job_repo),
):
    """Soft-delete a job — sets status to 'archived'. Existing candidates are preserved."""
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
 
    if job.status == JOB_STATUS_ARCHIVED:
        raise HTTPException(status_code=422, detail=f"Job {job_id!r} is already archived.")
 
    try:
        await job_repo.update_status(job_id, JOB_STATUS_ARCHIVED)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
 
    logger.info("job_archived", job_id=job_id, title=job.title)
    return SuccessResponse(data={"job_id": job_id, "status": JOB_STATUS_ARCHIVED})