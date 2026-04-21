"""Entities package. Re-exports all entity classes for convenience."""

from src.entities.batch import Batch
from src.entities.candidate import Candidate
from src.entities.evaluation_result import (
    EducationMatch,
    EvaluationResult,
    ExperienceMatch,
    RedFlag,
    SkillMatch,
)
from src.entities.extracted_document import ExtractedDocument, Section
from src.entities.job_requirement import JobRequirement

__all__ = [
    "Batch",
    "Candidate",
    "EducationMatch",
    "EvaluationResult",
    "ExperienceMatch",
    "ExtractedDocument",
    "JobRequirement",
    "RedFlag",
    "Section",
    "SkillMatch",
]
