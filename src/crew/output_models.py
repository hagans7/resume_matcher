"""Pydantic output models for CrewAI task output_pydantic.

Each model maps to one task in tasks.yaml.
CrewAI validates and parses agent output against these models.
OutputParser in clients/resume_matcher/output_parser.py
maps these into EvaluationResult entity.

Rules:
- All fields use simple types: str, int, bool, list[str]
- No nested Pydantic models — flat structure for reliable LLM output
- All list fields default to [] to handle partial outputs
- Notes fields default to "" so they are never None
"""

from pydantic import BaseModel, Field


class ResumeProfileOutput(BaseModel):
    """Output of profile_resume task — Resume Profiler agent."""
    name: str = Field(default="")
    skills: list[str] = Field(default_factory=list)
    experience_years: int = Field(default=0, ge=0)
    experience_summary: str = Field(default="")
    education_degree: str = Field(default="")
    education_field: str = Field(default="")
    certifications: list[str] = Field(default_factory=list)
    has_projects: bool = Field(default=False)
    project_names: list[str] = Field(default_factory=list)


class JDAnalysisOutput(BaseModel):
    """Output of analyze_jd task — JD Analyst agent."""
    title: str = Field(default="")
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_years: int = Field(default=0, ge=0)
    education_requirement: str = Field(default="")
    soft_skills_mentioned: list[str] = Field(default_factory=list)
    has_soft_skill_requirement: bool = Field(default=False)
    has_project_requirement: bool = Field(default=False)


class SkillMatchOutput(BaseModel):
    """Output of match_skills task — Skill Matcher agent."""
    score: int = Field(default=0, ge=0, le=100)
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    partial: list[str] = Field(default_factory=list)
    notes: str = Field(default="")


class ExperienceMatchOutput(BaseModel):
    """Output of evaluate_experience task — Experience Evaluator agent."""
    score: int = Field(default=0, ge=0, le=100)
    relevant_years: int = Field(default=0, ge=0)
    required_years: int = Field(default=0, ge=0)
    notes: str = Field(default="")


class EducationMatchOutput(BaseModel):
    """Output of assess_education task — Education Assessor agent."""
    score: int = Field(default=0, ge=0, le=100)
    meets_requirement: bool = Field(default=False)
    notes: str = Field(default="")


class RedFlagItem(BaseModel):
    type: str
    detail: str
    severity: str = Field(default="low")  # low | medium | high


class RedFlagOutput(BaseModel):
    """Output of detect_red_flags task — Red Flag Detector agent."""
    flags: list[RedFlagItem] = Field(default_factory=list)
    notes: str = Field(default="")


class SoftSkillOutput(BaseModel):
    """Output of analyze_soft_skills task — Soft Skill Analyzer agent (FULL profile only)."""
    score: int = Field(default=0, ge=0, le=100)
    notes: str = Field(default="")


class ProjectScoreOutput(BaseModel):
    """Output of score_projects task — Project Relevance Scorer agent (FULL profile only)."""
    score: int = Field(default=0, ge=0, le=100)
    notes: str = Field(default="")


class AggregatedScoreOutput(BaseModel):
    """Output of aggregate_scores task — Score Aggregator agent.

    Acts as context compressor: downstream Report Writer receives only this,
    not raw outputs from all previous agents (prevents 'lost in middle' syndrome).
    Keep output under 500 words — enforced in tasks.yaml description.
    """
    overall_score: int = Field(default=0, ge=0, le=100)
    verdict: str = Field(default="reject")  # shortlist | review | reject
    skill_score: int = Field(default=0, ge=0, le=100)
    experience_score: int = Field(default=0, ge=0, le=100)
    education_score: int = Field(default=0, ge=0, le=100)
    red_flag_count: int = Field(default=0, ge=0)
    key_strengths: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    aggregation_notes: str = Field(default="")


class ReportOutput(BaseModel):
    """Output of write_report task — Report Writer agent.

    Receives only AggregatedScoreOutput as context (not all previous tasks).
    This prevents 'lost in middle' LLM hallucination.
    """
    summary: str = Field(default="")
