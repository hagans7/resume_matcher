"""TaskFactory — loads tasks.yaml and creates CrewAI Task objects with context wiring.

Context resolution: dict lookup O(1) per reference.
Tasks are created in YAML order (already topologically sorted by dependency).
Context refs pointing to inactive tasks (not in active profile) are silently skipped.
"""

from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Task

from src.core.logging.logger import get_logger
from src.crew.output_models import (
    AggregatedScoreOutput,
    EducationMatchOutput,
    ExperienceMatchOutput,
    JDAnalysisOutput,
    ProjectScoreOutput,
    RedFlagOutput,
    ReportOutput,
    ResumeProfileOutput,
    SkillMatchOutput,
    SoftSkillOutput,
)

logger = get_logger(__name__)

# Module-level YAML cache
_tasks_config: dict[str, Any] | None = None
_YAML_PATH = Path(__file__).parent / "tasks.yaml"

# Maps task name → Pydantic output model for output_pydantic
OUTPUT_MODEL_MAP: dict[str, type] = {
    "profile_resume": ResumeProfileOutput,
    "analyze_jd": JDAnalysisOutput,
    "match_skills": SkillMatchOutput,
    "evaluate_experience": ExperienceMatchOutput,
    "assess_education": EducationMatchOutput,
    "detect_red_flags": RedFlagOutput,
    "analyze_soft_skills": SoftSkillOutput,
    "score_projects": ProjectScoreOutput,
    "aggregate_scores": AggregatedScoreOutput,
    "write_report": ReportOutput,
}


def _load_config() -> dict[str, Any]:
    """Load and cache tasks.yaml."""
    global _tasks_config
    if _tasks_config is None:
        with open(_YAML_PATH, "r", encoding="utf-8") as f:
            _tasks_config = yaml.safe_load(f)
        logger.debug("tasks_yaml_loaded", task_count=len(_tasks_config))
    return _tasks_config


def create_tasks(
    task_names: list[str],
    agents_map: dict[str, Agent],
    inputs: dict[str, str],
) -> list[Task]:
    """Create Task objects in order with context wiring.

    task_names must be in dependency order (guaranteed by builder._resolve_task_names).
    Context refs to tasks not in task_names are silently skipped (inactive profile agents).

    Args:
        task_names: ordered list of task names to create
        agents_map: name→Agent map from agent_factory
        inputs: dict with 'cv_text' and 'jd_text' for task description interpolation

    Returns:
        Ordered list of Task objects ready for Crew assembly.
    """
    config = _load_config()
    created: dict[str, Task] = {}  # name → Task, for context lookup

    for name in task_names:
        if name not in config:
            raise ValueError(f"Task '{name}' not found in tasks.yaml")

        task_cfg = config[name]
        agent_name = task_cfg["agent"]

        if agent_name not in agents_map:
            raise ValueError(
                f"Task '{name}' references agent '{agent_name}' "
                f"which is not in the active agent set."
            )

        # Interpolate cv_text and jd_text into task description
        description = task_cfg["description"].format(**inputs)

        # Resolve context: only include tasks that were actually created
        # (tasks from inactive agents are skipped gracefully)
        context_refs: list[str] = task_cfg.get("context", [])
        context_tasks = [
            created[ref] for ref in context_refs if ref in created
        ]

        output_model = OUTPUT_MODEL_MAP.get(name)

        task = Task(
            name=name, #improve: add name
            description=description,
            expected_output=task_cfg["expected_output"],
            agent=agents_map[agent_name],
            context=context_tasks,
            output_pydantic=output_model,
        )

        created[name] = task
        logger.debug(
            "task_created",
            name=name,
            agent=agent_name,
            context_count=len(context_tasks),
        )

    return list(created.values())
