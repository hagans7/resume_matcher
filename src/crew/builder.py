"""CrewBuilder — assembles a complete Crew object from profile + flags.

Thin orchestrator: all complex logic lives in factories.
Single responsibility: decide WHICH agents/tasks are active, then delegate.

Profile → agent/task selection:
  QUICK    → 4 agents  (profiler, jd_analyst, aggregator, writer)
  STANDARD → 7 agents  (+ skill_matcher, experience_evaluator, education_assessor)
  FULL     → 8-10 agents (+ red_flag_detector, optionally soft_skill, project_scorer)

Flags (set by EvaluateResumeService._determine_profile):
  include_soft_skill    → adds soft_skill_analyzer (FULL only)
  include_project_scorer → adds project_scorer (FULL only)
"""

from crewai import Crew, Process

from src.core.constants.app_constants import (
    EVALUATION_MODE_FULL,
    EVALUATION_MODE_QUICK,
    EVALUATION_MODE_STANDARD,
)
from src.core.logging.logger import get_logger
from src.crew import agent_factory, llm_factory, task_factory
from src.crew.callbacks.langfuse_tracer import CrewLangfuseTracer
from src.crew.callbacks.token_guard import TokenGuard
from src.interfaces.base_tracer_client import BaseTracerClient

logger = get_logger(__name__)

# Agent name → task name mapping (1:1 correspondence)
_AGENT_TO_TASK: dict[str, str] = {
    "resume_profiler": "profile_resume",
    "jd_analyst": "analyze_jd",
    "skill_matcher": "match_skills",
    "experience_evaluator": "evaluate_experience",
    "education_assessor": "assess_education",
    "red_flag_detector": "detect_red_flags",
    "soft_skill_analyzer": "analyze_soft_skills",
    "project_scorer": "score_projects",
    "score_aggregator": "aggregate_scores",
    "report_writer": "write_report",
}

# Base agent lists per profile (ordered by dependency)
_PROFILE_AGENTS: dict[str, list[str]] = {
    EVALUATION_MODE_QUICK: [
        "resume_profiler",
        "jd_analyst",
        "score_aggregator",
        "report_writer",
    ],
    EVALUATION_MODE_STANDARD: [
        "resume_profiler",
        "jd_analyst",
        "skill_matcher",
        "experience_evaluator",
        "education_assessor",
        "score_aggregator",
        "report_writer",
    ],
    EVALUATION_MODE_FULL: [
        "resume_profiler",
        "jd_analyst",
        "skill_matcher",
        "experience_evaluator",
        "education_assessor",
        "red_flag_detector",
        "score_aggregator",
        "report_writer",
    ],
}


def _resolve_agent_names(profile: str, flags: dict) -> list[str]:
    """Return ordered list of active agent names for this profile + flags.

    Conditional agents (soft_skill, project_scorer) are inserted before
    score_aggregator to maintain topological order.
    """
    if profile not in _PROFILE_AGENTS:
        raise ValueError(f"Unknown evaluation profile: {profile!r}")

    names = list(_PROFILE_AGENTS[profile])  # copy to avoid mutating module-level list

    if profile == EVALUATION_MODE_FULL:
        # Insert before score_aggregator (second-to-last position)
        insert_at = len(names) - 2  # before aggregator
        if flags.get("include_soft_skill"):
            names.insert(insert_at, "soft_skill_analyzer")
            insert_at += 1  # shift right for next insert
        if flags.get("include_project_scorer"):
            names.insert(insert_at, "project_scorer")

    return names


def _resolve_task_names(profile: str, flags: dict) -> list[str]:
    """Map resolved agent names to their corresponding task names."""
    agent_names = _resolve_agent_names(profile, flags)
    return [_AGENT_TO_TASK[name] for name in agent_names]


def build_crew(
    profile: str,
    flags: dict,
    llm_model: str,
    llm_api_key: str,
    llm_base_url: str | None,
    llm_max_rpm: int,
    llm_verbose: bool,
    token_budget: int,
    tracer: BaseTracerClient,
    trace_id: str,
    inputs: dict[str, str],
) -> Crew:
    """Assemble and return a configured Crew object.

    Args:
        profile: EVALUATION_MODE_QUICK | STANDARD | FULL
        flags: {'include_soft_skill': bool, 'include_project_scorer': bool}
        llm_*: LLM configuration from settings
        token_budget: max tokens for this crew run
        tracer: BaseTracerClient implementation (Langfuse or null)
        trace_id: unique ID for this evaluation (candidate_id)
        inputs: {'cv_text': str, 'jd_text': str} for task description interpolation
    """
    agent_names = _resolve_agent_names(profile, flags)
    task_names = _resolve_task_names(profile, flags)

    logger.info(
        "crew_building",
        profile=profile,
        flags=flags,
        agent_count=len(agent_names),
        agents=agent_names,
    )

    # 1. Create LLM
    llm = llm_factory.create_llm(
        model=llm_model,
        api_key=llm_api_key,
        base_url=llm_base_url,
        max_rpm=llm_max_rpm,
        verbose=llm_verbose,
    )

    # 2. Create agents
    agents_map = agent_factory.create_agents(agent_names, llm)

    # 3. Create tasks with context wiring + input interpolation
    tasks = task_factory.create_tasks(task_names, agents_map, inputs)

    # 4. Setup callbacks
    token_guard = TokenGuard(budget=token_budget)
    crew_tracer = CrewLangfuseTracer(tracer=tracer, trace_id=trace_id)

    # 5. Assemble Crew
    crew = Crew(
        agents=list(agents_map.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=llm_verbose,
        step_callback=token_guard.check,
        task_callback=crew_tracer.on_task_complete,
    )

    logger.info("crew_built", profile=profile, task_count=len(tasks))
    return crew, token_guard
