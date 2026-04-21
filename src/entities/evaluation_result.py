"""EvaluationResult and sub-entities.

Represents the structured output from the CrewAI evaluation pipeline.
Carries versioning fields (crew_version, llm_model) for full reproducibility.

to_dict / from_dict kept flat (max 2 levels deep) — no recursive serialization.
Used for JSONB storage in candidate_orm.result_json.
"""

from dataclasses import asdict, dataclass, field


@dataclass
class SkillMatch:
    score: int                  # 0–100
    matched: list[str]          # skills present in CV and required in JD
    missing: list[str]          # required skills absent from CV
    partial: list[str]          # skills with alias/partial match
    notes: str


@dataclass
class ExperienceMatch:
    score: int                  # 0–100
    relevant_years: int         # years of domain-relevant experience in CV
    required_years: int         # minimum years stated in JD
    notes: str


@dataclass
class EducationMatch:
    score: int                  # 0–100
    meets_requirement: bool
    notes: str


@dataclass
class RedFlag:
    type: str                   # employment_gap | job_hopping | inconsistent_dates | overqualified
    detail: str
    severity: str               # low | medium | high


@dataclass
class EvaluationResult:
    overall_score: int          # 0–100, weighted aggregate
    verdict: str                # shortlist | review | reject
    skill_match: SkillMatch
    experience_match: ExperienceMatch
    education_match: EducationMatch
    red_flags: list[RedFlag]
    summary: str                # human-readable executive summary (Report Writer output)
    token_used: int
    processing_ms: int
    crew_version: str           # from crew/version.py — links result to exact crew config
    llm_model: str              # from settings.llm_model — links result to model version
    soft_skill_notes: str | None = None     # populated only in FULL profile
    project_relevance_notes: str | None = None  # populated only in FULL profile with projects

    def to_dict(self) -> dict:
        """Serialize to flat-ish dict for JSONB storage. Max 2 levels deep."""
        return {
            "overall_score": self.overall_score,
            "verdict": self.verdict,
            "skill_match": asdict(self.skill_match),
            "experience_match": asdict(self.experience_match),
            "education_match": asdict(self.education_match),
            "red_flags": [asdict(rf) for rf in self.red_flags],
            "summary": self.summary,
            "token_used": self.token_used,
            "processing_ms": self.processing_ms,
            "crew_version": self.crew_version,
            "llm_model": self.llm_model,
            "soft_skill_notes": self.soft_skill_notes,
            "project_relevance_notes": self.project_relevance_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationResult":
        """Deserialize from JSONB dict. Raises KeyError if required fields missing."""
        return cls(
            overall_score=data["overall_score"],
            verdict=data["verdict"],
            skill_match=SkillMatch(**data["skill_match"]),
            experience_match=ExperienceMatch(**data["experience_match"]),
            education_match=EducationMatch(**data["education_match"]),
            red_flags=[RedFlag(**rf) for rf in data.get("red_flags", [])],
            summary=data["summary"],
            token_used=data["token_used"],
            processing_ms=data["processing_ms"],
            crew_version=data["crew_version"],
            llm_model=data["llm_model"],
            soft_skill_notes=data.get("soft_skill_notes"),
            project_relevance_notes=data.get("project_relevance_notes"),
        )
