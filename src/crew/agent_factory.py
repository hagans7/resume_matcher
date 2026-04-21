"""AgentFactory — loads agents.yaml and creates CrewAI Agent objects.

Module-level YAML cache: loaded once, reused across all crew builds.
O(1) after first load.
"""

from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, LLM

from src.core.logging.logger import get_logger

logger = get_logger(__name__)

# Module-level cache: None until first load
_agents_config: dict[str, Any] | None = None
_YAML_PATH = Path(__file__).parent / "agents.yaml"


def _load_config() -> dict[str, Any]:
    """Load and cache agents.yaml. Thread-safe via GIL for read-only dict."""
    global _agents_config
    if _agents_config is None:
        with open(_YAML_PATH, "r", encoding="utf-8") as f:
            _agents_config = yaml.safe_load(f)
        logger.debug("agents_yaml_loaded", agent_count=len(_agents_config))
    return _agents_config


def create_agents(names: list[str], llm: LLM) -> dict[str, Agent]:
    """Create Agent objects for the specified agent names only.

    Returns name→Agent dict. Only creates agents in the active profile.
    O(n) where n = number of active agents (max 10).
    """
    config = _load_config()
    agents: dict[str, Agent] = {}

    for name in names:
        if name not in config:
            raise ValueError(f"Agent '{name}' not found in agents.yaml")

        agent_cfg = config[name]
        agents[name] = Agent(
            role=agent_cfg["role"],
            goal=agent_cfg["goal"],
            backstory=agent_cfg["backstory"],
            llm=llm,
            verbose=agent_cfg.get("verbose", False),
            max_iter=agent_cfg.get("max_iter", 3),
            allow_delegation=False,  # always disabled — agents don't sub-delegate
        )
        logger.debug("agent_created", name=name)

    return agents
