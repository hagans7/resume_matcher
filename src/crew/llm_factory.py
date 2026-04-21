"""LLM factory — creates CrewAI LLM instance from settings.

Single responsibility: config → LLM object.
Provider swap: change LLM_BASE_URL + LLM_MODEL env vars only.
No code change needed.

OpenRouter model name format for LiteLLM:
  LiteLLM routes via base_url, so model name is passed as-is.
  For OpenRouter: use "openrouter/<provider>/<model>" OR just "<provider>/<model>"
  depending on LiteLLM version. We use the base_url + model pattern which is
  the most stable approach across versions.
"""

from crewai import LLM

from src.core.logging.logger import get_logger

logger = get_logger(__name__)


def create_llm(
    model: str,
    api_key: str,
    base_url: str | None,
    max_rpm: int,
    verbose: bool,
) -> LLM:
    """Create and return a configured CrewAI LLM instance.

    Supports any OpenAI-compatible endpoint via base_url.
    For OpenRouter: base_url=https://openrouter.ai/api/v1, model=qwen/qwen3-6b-plus:free
    """
    llm_kwargs: dict = {
        "model": model,
        "api_key": api_key,
        "max_tokens": 4096,
    }

    if base_url:
        llm_kwargs["base_url"] = base_url

    llm = LLM(**llm_kwargs)

    logger.info(
        "llm_created",
        model=model,
        base_url=base_url or "default (OpenAI)",
        max_rpm=max_rpm,
    )
    return llm
