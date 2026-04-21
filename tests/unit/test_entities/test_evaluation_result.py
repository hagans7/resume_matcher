"""Unit tests for EvaluationResult entity — to_dict / from_dict roundtrip."""

from src.entities.evaluation_result import (
    EducationMatch,
    EvaluationResult,
    ExperienceMatch,
    RedFlag,
    SkillMatch,
)


def _make_result(**kwargs) -> EvaluationResult:
    defaults = dict(
        overall_score=78,
        verdict="shortlist",
        skill_match=SkillMatch(score=85, matched=["Python"], missing=["Docker"], partial=[], notes="ok"),
        experience_match=ExperienceMatch(score=70, relevant_years=2, required_years=3, notes="close"),
        education_match=EducationMatch(score=80, meets_requirement=True, notes="good"),
        red_flags=[RedFlag(type="employment_gap", detail="6 months", severity="low")],
        summary="Good candidate.",
        token_used=1200,
        processing_ms=2500,
        crew_version="1.0.0",
        llm_model="qwen/qwen3-6b-plus:free",
    )
    defaults.update(kwargs)
    return EvaluationResult(**defaults)


class TestEvaluationResultRoundtrip:
    def test_to_dict_and_back(self):
        original = _make_result()
        d = original.to_dict()
        restored = EvaluationResult.from_dict(d)

        assert restored.overall_score == original.overall_score
        assert restored.verdict == original.verdict
        assert restored.skill_match.score == original.skill_match.score
        assert restored.skill_match.matched == original.skill_match.matched
        assert restored.experience_match.relevant_years == original.experience_match.relevant_years
        assert restored.education_match.meets_requirement == original.education_match.meets_requirement
        assert len(restored.red_flags) == 1
        assert restored.red_flags[0].type == "employment_gap"
        assert restored.crew_version == "1.0.0"
        assert restored.llm_model == "qwen/qwen3-6b-plus:free"

    def test_to_dict_has_all_required_keys(self):
        d = _make_result().to_dict()
        required = {
            "overall_score", "verdict", "skill_match", "experience_match",
            "education_match", "red_flags", "summary", "token_used",
            "processing_ms", "crew_version", "llm_model",
        }
        assert required.issubset(d.keys())

    def test_optional_fields_default_to_none(self):
        result = _make_result()
        d = result.to_dict()
        assert d["soft_skill_notes"] is None
        assert d["project_relevance_notes"] is None

    def test_optional_fields_roundtrip(self):
        result = _make_result(
            soft_skill_notes="Good communicator",
            project_relevance_notes="Relevant projects",
        )
        restored = EvaluationResult.from_dict(result.to_dict())
        assert restored.soft_skill_notes == "Good communicator"
        assert restored.project_relevance_notes == "Relevant projects"

    def test_empty_red_flags(self):
        result = _make_result(red_flags=[])
        restored = EvaluationResult.from_dict(result.to_dict())
        assert restored.red_flags == []
