"""Evaluation API schemas.

Gap fix: EvaluationResultData uses typed nested models instead of plain dict.
This gives stable API contract that frontend can rely on.
"""

from datetime import datetime

from pydantic import BaseModel


# ── Nested result components ──────────────────────────────────────────────────

class SkillMatchData(BaseModel):
    score: int
    matched: list[str]
    missing: list[str]
    partial: list[str]
    notes: str


class ExperienceMatchData(BaseModel):
    score: int
    relevant_years: int
    required_years: int
    notes: str


class EducationMatchData(BaseModel):
    score: int
    meets_requirement: bool
    notes: str


class RedFlagData(BaseModel):
    type: str
    detail: str
    severity: str


# ── Top-level result ──────────────────────────────────────────────────────────

class EvaluationResultData(BaseModel):
    overall_score: int
    verdict: str
    skill_match: SkillMatchData
    experience_match: ExperienceMatchData
    education_match: EducationMatchData
    red_flags: list[RedFlagData]
    summary: str
    token_used: int
    processing_ms: int
    crew_version: str
    llm_model: str
    soft_skill_notes: str | None = None
    project_relevance_notes: str | None = None


# ── Endpoint schemas ──────────────────────────────────────────────────────────

class EvaluateResponse(BaseModel):
    candidate_id: str
    job_id: str
    original_filename: str
    status: str
    score: int | None = None
    verdict: str | None = None
    result: EvaluationResultData | None = None
