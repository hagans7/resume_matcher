"""Single CV evaluation route — POST /evaluate."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.api.schemas.base_schema import SuccessResponse
from src.api.schemas.evaluation_schema import EvaluateResponse, EvaluationResultData
from src.core.exceptions.app_exceptions import (
    CrewExecutionError,
    CrewTimeoutError,
    DocumentExtractionError,
    DuplicateCVError,
    FileValidationError,
    FileTooLargeError,
    JobNotFoundError,
    ValidationError,
)
from src.core.logging.logger import get_logger
from src.entities.candidate import Candidate
from src.entities.evaluation_result import EvaluationResult
from src.providers import get_evaluate_resume_service
from src.services.evaluate_resume import EvaluateResumeService

router = APIRouter(prefix="/evaluate", tags=["evaluation"])
logger = get_logger(__name__)


def _build_result_data(result_json: dict | None) -> EvaluationResultData | None:
    """Reconstruct typed result from JSONB dict."""
    if result_json is None:
        return None
    try:
        entity = EvaluationResult.from_dict(result_json)
        from src.api.schemas.evaluation_schema import (
            EducationMatchData, ExperienceMatchData,
            RedFlagData, SkillMatchData,
        )
        return EvaluationResultData(
            overall_score=entity.overall_score,
            verdict=entity.verdict,
            skill_match=SkillMatchData(**vars(entity.skill_match)),
            experience_match=ExperienceMatchData(**vars(entity.experience_match)),
            education_match=EducationMatchData(**vars(entity.education_match)),
            red_flags=[RedFlagData(**vars(rf)) for rf in entity.red_flags],
            summary=entity.summary,
            token_used=entity.token_used,
            processing_ms=entity.processing_ms,
            crew_version=entity.crew_version,
            llm_model=entity.llm_model,
            soft_skill_notes=entity.soft_skill_notes,
            project_relevance_notes=entity.project_relevance_notes,
        )
    except Exception as exc:
        logger.warning("result_data_build_failed", error=str(exc))
        return None


def _to_response(candidate: Candidate) -> EvaluateResponse:
    return EvaluateResponse(
        candidate_id=candidate.id,
        job_id=candidate.job_id,
        original_filename=candidate.original_filename,
        status=candidate.status,
        score=candidate.score,
        verdict=candidate.verdict,
        result=_build_result_data(candidate.result_json),
    )


@router.post("", response_model=SuccessResponse)
async def evaluate_single(
    job_id: str = Form(...),
    file: UploadFile = File(...),
    service: EvaluateResumeService = Depends(get_evaluate_resume_service),
):
    """Evaluate a single CV against a job requirement. Synchronous — waits for result."""
    file_bytes = await file.read()
    filename = file.filename or "upload.pdf"

    try:
        candidate = await service.execute(
            job_id=job_id,
            file_bytes=file_bytes,
            filename=filename,
        )
        return SuccessResponse(data=_to_response(candidate))

    except (FileValidationError, FileTooLargeError) as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except DuplicateCVError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=f"CV could not be parsed: {exc.message}")
    except CrewTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Evaluation timed out. Try again later.")
    except CrewExecutionError as exc:
        logger.error("evaluation_crew_error", error=exc.message)
        raise HTTPException(status_code=503, detail="Evaluation service unavailable.")
