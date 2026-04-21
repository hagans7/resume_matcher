"""Batch processing routes — POST /batch, GET /batch/{batch_id}."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from typing import Annotated

from src.api.schemas.base_schema import SuccessResponse
from src.api.schemas.batch_schema import BatchStatusResponse, BatchSubmitResponse
from src.core.exceptions.app_exceptions import (
    FileValidationError,
    FileTooLargeError,
    JobNotFoundError,
    ValidationError,
)
from src.core.logging.logger import get_logger
from src.providers import get_check_batch_status_service, get_submit_batch_service
from src.services.check_batch_status import CheckBatchStatusService
from src.services.submit_batch import SubmitBatchService

router = APIRouter(prefix="/batch", tags=["batch"])
logger = get_logger(__name__)


@router.post("", response_model=SuccessResponse, status_code=202)
async def submit_batch(
    job_id: str = Form(...),
    files: list[UploadFile] = File(...),
    service: SubmitBatchService = Depends(get_submit_batch_service),
):
    """Submit multiple CVs for async batch evaluation.

    Returns immediately with batch_id. Poll GET /batch/{batch_id} for progress.
    """
    file_tuples: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        filename = upload.filename or "upload.pdf"
        file_tuples.append((filename, content))

    try:
        batch = await service.execute(job_id=job_id, files=file_tuples)
        return SuccessResponse(
            data=BatchSubmitResponse(
                batch_id=batch.id,
                job_id=batch.job_id,
                status=batch.status,
                total=batch.total,
            )
        )
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except (FileValidationError, FileTooLargeError) as exc:
        raise HTTPException(status_code=422, detail=exc.message)


@router.get("/{batch_id}", response_model=SuccessResponse)
async def get_batch_status(
    batch_id: str,
    service: CheckBatchStatusService = Depends(get_check_batch_status_service),
):
    """Poll batch evaluation progress."""
    from src.core.exceptions.app_exceptions import BatchNotFoundError
    try:
        result = await service.execute(batch_id)
        return SuccessResponse(
            data=BatchStatusResponse(
                batch_id=result["batch_id"],
                job_id=result["job_id"],
                status=result["status"],
                total=result["total"],
                succeeded=result["succeeded"],
                failed=result["failed"],
                progress_percent=result["progress_percent"],
                candidate_counts=result["candidate_counts"],
            )
        )
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
