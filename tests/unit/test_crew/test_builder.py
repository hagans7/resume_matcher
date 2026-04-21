"""Unit tests for crew builder — profile and flag resolution logic."""

import pytest

from src.core.constants.app_constants import (
    EVALUATION_MODE_FULL,
    EVALUATION_MODE_QUICK,
    EVALUATION_MODE_STANDARD,
)
from src.crew.builder import _resolve_agent_names, _resolve_task_names


class TestResolveAgentNames:
    def test_quick_has_4_agents(self):
        names = _resolve_agent_names(EVALUATION_MODE_QUICK, {})
        assert len(names) == 4
        assert "resume_profiler" in names
        assert "jd_analyst" in names
        assert "score_aggregator" in names
        assert "report_writer" in names

    def test_standard_has_7_agents(self):
        names = _resolve_agent_names(EVALUATION_MODE_STANDARD, {})
        assert len(names) == 7
        assert "skill_matcher" in names
        assert "experience_evaluator" in names
        assert "education_assessor" in names

    def test_full_base_has_8_agents(self):
        names = _resolve_agent_names(EVALUATION_MODE_FULL, {})
        assert len(names) == 8
        assert "red_flag_detector" in names

    def test_full_with_soft_skill_flag(self):
        names = _resolve_agent_names(EVALUATION_MODE_FULL, {"include_soft_skill": True})
        assert "soft_skill_analyzer" in names
        assert len(names) == 9

    def test_full_with_project_scorer_flag(self):
        names = _resolve_agent_names(EVALUATION_MODE_FULL, {"include_project_scorer": True})
        assert "project_scorer" in names
        assert len(names) == 9

    def test_full_with_both_flags(self):
        names = _resolve_agent_names(
            EVALUATION_MODE_FULL,
            {"include_soft_skill": True, "include_project_scorer": True},
        )
        assert "soft_skill_analyzer" in names
        assert "project_scorer" in names
        assert len(names) == 10

    def test_soft_skill_not_added_for_standard(self):
        names = _resolve_agent_names(EVALUATION_MODE_STANDARD, {"include_soft_skill": True})
        assert "soft_skill_analyzer" not in names

    def test_aggregator_always_before_writer(self):
        for profile in [EVALUATION_MODE_QUICK, EVALUATION_MODE_STANDARD, EVALUATION_MODE_FULL]:
            names = _resolve_agent_names(profile, {})
            agg_idx = names.index("score_aggregator")
            writer_idx = names.index("report_writer")
            assert agg_idx < writer_idx, f"Aggregator must come before writer in {profile}"

    def test_conditional_agents_before_aggregator(self):
        names = _resolve_agent_names(
            EVALUATION_MODE_FULL,
            {"include_soft_skill": True, "include_project_scorer": True},
        )
        agg_idx = names.index("score_aggregator")
        soft_idx = names.index("soft_skill_analyzer")
        proj_idx = names.index("project_scorer")
        assert soft_idx < agg_idx
        assert proj_idx < agg_idx

    def test_invalid_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown evaluation profile"):
            _resolve_agent_names("invalid_profile", {})


class TestResolveTaskNames:
    def test_task_count_matches_agent_count(self):
        for profile in [EVALUATION_MODE_QUICK, EVALUATION_MODE_STANDARD, EVALUATION_MODE_FULL]:
            agents = _resolve_agent_names(profile, {})
            tasks = _resolve_task_names(profile, {})
            assert len(tasks) == len(agents)

    def test_task_order_matches_agent_order(self):
        task_names = _resolve_task_names(EVALUATION_MODE_STANDARD, {})
        expected = [
            "profile_resume", "analyze_jd", "match_skills",
            "evaluate_experience", "assess_education",
            "aggregate_scores", "write_report",
        ]
        assert task_names == expected

    def test_write_report_always_last(self):
        for profile in [EVALUATION_MODE_QUICK, EVALUATION_MODE_STANDARD, EVALUATION_MODE_FULL]:
            tasks = _resolve_task_names(profile, {})
            assert tasks[-1] == "write_report"

    def test_aggregate_scores_always_second_to_last(self):
        for profile in [EVALUATION_MODE_QUICK, EVALUATION_MODE_STANDARD, EVALUATION_MODE_FULL]:
            tasks = _resolve_task_names(profile, {})
            assert tasks[-2] == "aggregate_scores"
