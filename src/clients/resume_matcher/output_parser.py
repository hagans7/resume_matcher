"""OutputParser — maps raw CrewAI crew output to EvaluationResult entity.

Receives the final crew kickoff result and extracts per-task outputs.
Uses Pydantic output_pydantic models (already validated by CrewAI).
Maps to domain entities: EvaluationResult, SkillMatch, etc.

Linear scan of task outputs: O(n) where n ≤ 10.
"""

from crewai import Crew

from src.core.logging.logger import get_logger
from src.crew.output_models import (
    AggregatedScoreOutput,
    EducationMatchOutput,
    ExperienceMatchOutput,
    RedFlagOutput,
    ReportOutput,
    SkillMatchOutput,
    SoftSkillOutput,
    ProjectScoreOutput,
)
from src.entities.evaluation_result import (
    EducationMatch,
    EvaluationResult,
    ExperienceMatch,
    RedFlag,
    SkillMatch,
)

logger = get_logger(__name__)


def parse_crew_output(
    crew_output,
    token_used: int,
    processing_ms: int,
    crew_version: str,
    llm_model: str,
) -> EvaluationResult:
    """Map CrewAI crew kickoff output to EvaluationResult entity.

    crew_output: CrewOutput object returned by crew.kickoff()
    Raises ValueError if required task outputs are missing.
    """
    # Build name → parsed pydantic output map from all task outputs
    task_outputs: dict[str, object] = {}

    if hasattr(crew_output, "tasks_output") and crew_output.tasks_output:
        for task_out in crew_output.tasks_output:
            task_name = _extract_task_name(task_out)
            parsed = task_out.pydantic if hasattr(task_out, "pydantic") else None
            if task_name and parsed is not None:
                task_outputs[task_name] = parsed
                logger.debug("task_output_parsed", task=task_name, type=type(parsed).__name__)

    # Required outputs — raise if missing
    aggregated: AggregatedScoreOutput = _require(
        task_outputs, "aggregate_scores", AggregatedScoreOutput
    )
    report: ReportOutput = _require(task_outputs, "write_report", ReportOutput)

    # Optional outputs — may be None if agent was not in profile
    skill_out: SkillMatchOutput | None = task_outputs.get("match_skills")
    exp_out: ExperienceMatchOutput | None = task_outputs.get("evaluate_experience")
    edu_out: EducationMatchOutput | None = task_outputs.get("assess_education")
    red_out: RedFlagOutput | None = task_outputs.get("detect_red_flags")
    soft_out: SoftSkillOutput | None = task_outputs.get("analyze_soft_skills")
    proj_out: ProjectScoreOutput | None = task_outputs.get("score_projects")

    # Build sub-entities with safe fallbacks for QUICK profile
    skill_match = SkillMatch(
        score=skill_out.score if skill_out else aggregated.skill_score,
        matched=skill_out.matched if skill_out else [],
        missing=skill_out.missing if skill_out else [],
        partial=skill_out.partial if skill_out else [],
        notes=skill_out.notes if skill_out else "",
    )

    experience_match = ExperienceMatch(
        score=exp_out.score if exp_out else aggregated.experience_score,
        relevant_years=exp_out.relevant_years if exp_out else 0,
        required_years=exp_out.required_years if exp_out else 0,
        notes=exp_out.notes if exp_out else "",
    )

    education_match = EducationMatch(
        score=edu_out.score if edu_out else aggregated.education_score,
        meets_requirement=edu_out.meets_requirement if edu_out else False,
        notes=edu_out.notes if edu_out else "",
    )

    red_flags = []
    if red_out and red_out.flags:
        red_flags = [
            RedFlag(type=f.type, detail=f.detail, severity=f.severity)
            for f in red_out.flags
        ]

    result = EvaluationResult(
        overall_score=aggregated.overall_score,
        verdict=aggregated.verdict,
        skill_match=skill_match,
        experience_match=experience_match,
        education_match=education_match,
        red_flags=red_flags,
        summary=report.summary,
        token_used=token_used,
        processing_ms=processing_ms,
        crew_version=crew_version,
        llm_model=llm_model,
        soft_skill_notes=soft_out.notes if soft_out else None,
        project_relevance_notes=proj_out.notes if proj_out else None,
    )

    logger.info(
        "crew_output_parsed",
        overall_score=result.overall_score,
        verdict=result.verdict,
        token_used=token_used,
        processing_ms=processing_ms,
    )
    return result


def _require(task_outputs: dict, name: str, expected_type: type) -> object:
    """Get required task output. Raises ValueError if missing."""
    out = task_outputs.get(name)
    if out is None:
        raise ValueError(
            f"Required task output '{name}' missing from crew result. "
            f"Check that '{name}' task ran and produced valid output."
        )
    return out


def _extract_task_name(task_out) -> str | None:
    """Extract task name from CrewAI task output object."""
    try:
        if hasattr(task_out, "task") and hasattr(task_out.task, "name"):
            return task_out.task.name
        if hasattr(task_out, "name"):
            return task_out.name
        # Fallback: infer from pydantic model type
        if hasattr(task_out, "pydantic") and task_out.pydantic is not None:
            type_name = type(task_out.pydantic).__name__
            _type_to_task = {
                "ResumeProfileOutput": "profile_resume",
                "JDAnalysisOutput": "analyze_jd",
                "SkillMatchOutput": "match_skills",
                "ExperienceMatchOutput": "evaluate_experience",
                "EducationMatchOutput": "assess_education",
                "RedFlagOutput": "detect_red_flags",
                "SoftSkillOutput": "analyze_soft_skills",
                "ProjectScoreOutput": "score_projects",
                "AggregatedScoreOutput": "aggregate_scores",
                "ReportOutput": "write_report",
            }
            return _type_to_task.get(type_name)
    except Exception:
        pass
    return None
