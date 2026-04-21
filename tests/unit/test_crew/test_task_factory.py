"""Unit tests for TaskFactory — verifies Task name assignment and context wiring.

Bug guard: crewai Task objects MUST have name= set explicitly.
Without it, output_parser._extract_task_name() cannot find outputs by name,
causing parse failures and 503 errors on evaluation endpoints.
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_agent(name: str):
    """Create a minimal mock Agent that satisfies TaskFactory expectations."""
    agent = MagicMock()
    agent.role = name
    return agent


class TestTaskFactoryNameAssignment:
    """Ensure every created Task has explicit name= matching the YAML key."""

    def test_task_has_explicit_name_attribute(self):
        """Task created by factory must have .name == the task key in YAML."""
        mock_agents = {
            "score_aggregator": _make_mock_agent("score_aggregator"),
        }
        inputs = {"cv_text": "Hagan CV", "jd_text": "Python Dev"}

        # Patch Task to capture constructor args without needing real crewai
        captured_kwargs = {}

        class CapturingTask:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)
                self.name = kwargs.get("name")
                self.description = kwargs.get("description", "")
                self.context = kwargs.get("context", [])

        with patch("src.crew.task_factory.Task", CapturingTask):
            from src.crew import task_factory
            # Reset module-level cache so YAML is reloaded
            task_factory._tasks_config = None

            tasks = task_factory.create_tasks(
                task_names=["aggregate_scores"],
                agents_map=mock_agents,
                inputs=inputs,
            )

        assert len(tasks) == 1
        created = tasks[0]

        # Core assertion: name must be set explicitly (was the bug)
        assert hasattr(created, "name"), "Task missing 'name' attribute"
        assert created.name == "aggregate_scores", (
            f"Expected name='aggregate_scores', got {created.name!r}. "
            "Ensure task_factory passes name=name to Task()"
        )

    def test_all_created_tasks_have_correct_names(self):
        """Multi-task creation: each task name matches its YAML key."""
        mock_agents = {
            "score_aggregator": _make_mock_agent("score_aggregator"),
            "report_writer": _make_mock_agent("report_writer"),
        }
        inputs = {"cv_text": "test cv", "jd_text": "test jd"}

        created_tasks = []

        class CapturingTask:
            def __init__(self, **kwargs):
                self.name = kwargs.get("name")
                self.context = kwargs.get("context", [])

        with patch("src.crew.task_factory.Task", CapturingTask):
            from src.crew import task_factory
            task_factory._tasks_config = None

            tasks = task_factory.create_tasks(
                task_names=["aggregate_scores", "write_report"],
                agents_map=mock_agents,
                inputs=inputs,
            )

        names = [t.name for t in tasks]
        assert "aggregate_scores" in names
        assert "write_report" in names

    def test_task_missing_from_yaml_raises_value_error(self):
        """Requesting a non-existent task name raises ValueError immediately."""
        mock_agents = {"nonexistent_agent": _make_mock_agent("nonexistent_agent")}
        inputs = {"cv_text": "x", "jd_text": "x"}

        with patch("src.crew.task_factory.Task", MagicMock()):
            from src.crew import task_factory
            task_factory._tasks_config = None

            with pytest.raises(ValueError, match="not found in tasks.yaml"):
                task_factory.create_tasks(
                    task_names=["totally_nonexistent_task_xyz"],
                    agents_map=mock_agents,
                    inputs=inputs,
                )

    def test_agent_not_in_active_set_raises_value_error(self):
        """Task referencing an agent not in agents_map raises ValueError."""
        # aggregate_scores expects 'score_aggregator' — we provide wrong agent
        mock_agents = {"wrong_agent": _make_mock_agent("wrong_agent")}
        inputs = {"cv_text": "x", "jd_text": "x"}

        with patch("src.crew.task_factory.Task", MagicMock()):
            from src.crew import task_factory
            task_factory._tasks_config = None

            with pytest.raises(ValueError, match="references agent"):
                task_factory.create_tasks(
                    task_names=["aggregate_scores"],
                    agents_map=mock_agents,
                    inputs=inputs,
                )