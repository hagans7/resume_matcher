"""Unit tests for OutputParser — verifies error handling when AI output is incomplete.

Bug guard: if AI fails to produce required task outputs (aggregate_scores, write_report),
the parser must raise ValueError — not silently return None or crash with AttributeError.
A ValueError at this layer gets caught by the crew client and translated to a
structured CrewExecutionError, returning HTTP 422/500 instead of 503.
"""

import pytest


class MockPydantic:
    """Generic mock pydantic output for any task."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockTaskOutput:
    """Simulates a single CrewAI task output object."""
    def __init__(self, name: str, pydantic_data=None):
        self.name = name
        self.pydantic = pydantic_data


class MockCrewOutput:
    """Simulates the full crew kickoff result."""
    def __init__(self, tasks_output: list):
        self.tasks_output = tasks_output


def _call_parser(tasks_output: list) -> object:
    """Helper: call parse_crew_output with given mock task outputs."""
    from src.clients.resume_matcher.output_parser import parse_crew_output
    return parse_crew_output(
        crew_output=MockCrewOutput(tasks_output=tasks_output),
        token_used=100,
        processing_ms=2000,
        crew_version="1.0.0",
        llm_model="test-model",
    )


class TestCrewOutputParserMissingTasks:
    """Parser must raise ValueError for missing required tasks."""

    def test_missing_aggregate_scores_raises_value_error(self):
        """aggregate_scores is required — missing it must raise ValueError."""
        tasks = [
            MockTaskOutput("write_report", MockPydantic(summary="Good candidate")),
        ]
        with pytest.raises(ValueError) as exc_info:
            _call_parser(tasks)
        assert "aggregate_scores" in str(exc_info.value)
        assert "missing from crew result" in str(exc_info.value)

    def test_missing_write_report_raises_value_error(self):
        """write_report is required — missing it must raise ValueError."""
        # Build a minimal aggregated output
        agg = MockPydantic(
            overall_score=75,
            verdict="shortlist",
            skill_score=80,
            experience_score=70,
            education_score=75,
            soft_skill_score=None,
            project_score=None,
            red_flag_count=0,
            confidence="high",
            reasoning="Good match",
        )
        tasks = [
            MockTaskOutput("aggregate_scores", agg),
        ]
        with pytest.raises(ValueError) as exc_info:
            _call_parser(tasks)
        assert "write_report" in str(exc_info.value)
        assert "missing from crew result" in str(exc_info.value)

    def test_empty_tasks_output_raises_value_error(self):
        """No task outputs at all must raise ValueError."""
        with pytest.raises(ValueError):
            _call_parser([])

    def test_tasks_with_none_pydantic_are_skipped(self):
        """Tasks where pydantic=None should not be treated as valid outputs."""
        # Even if task name exists, None pydantic means it wasn't parsed
        tasks = [
            MockTaskOutput("aggregate_scores", None),   # pydantic is None
            MockTaskOutput("write_report", None),        # pydantic is None
        ]
        with pytest.raises(ValueError):
            _call_parser(tasks)

    def test_wrong_task_names_raise_value_error(self):
        """Outputs with unexpected names don't satisfy required task check."""
        tasks = [
            MockTaskOutput("some_other_task", MockPydantic(data="x")),
            MockTaskOutput("another_task", MockPydantic(data="y")),
        ]
        with pytest.raises(ValueError) as exc_info:
            _call_parser(tasks)
        # Should mention the first missing required task
        error_msg = str(exc_info.value)
        assert "aggregate_scores" in error_msg or "write_report" in error_msg


class TestCrewOutputParserValidOutput:
    """Parser produces correct EvaluationResult when all required tasks present."""

    def test_standard_profile_full_output(self):
        """With both required tasks, parser returns EvaluationResult entity."""
        from src.entities.evaluation_result import EvaluationResult

        agg = MockPydantic(
            overall_score=82,
            verdict="shortlist",
            skill_score=85,
            experience_score=78,
            education_score=80,
            soft_skill_score=None,
            project_score=None,
            red_flag_count=0,
            confidence="high",
            reasoning="Strong Python background",
        )
        report = MockPydantic(
            summary="Candidate is well-suited for the role.",
            strengths=["Python", "FastAPI"],
            weaknesses=["Docker"],
            recommendation="Proceed to interview",
        )
        tasks = [
            MockTaskOutput("aggregate_scores", agg),
            MockTaskOutput("write_report", report),
        ]

        result = _call_parser(tasks)

        assert isinstance(result, EvaluationResult)
        assert result.overall_score == 82
        assert result.verdict == "shortlist"
        assert result.summary == "Candidate is well-suited for the role."
        assert result.token_used == 100
        assert result.processing_ms == 2000
        assert result.crew_version == "1.0.0"