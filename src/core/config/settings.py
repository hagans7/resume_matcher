"""Application configuration.

Single source of truth for all config values.
All fields are read from environment variables via pydantic-settings.
No defaults for security-critical fields (LLM_API_KEY, DATABASE_URL, REDIS_URL).
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration, grouped by concern."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_env: str = Field(default="dev", description="Runtime environment: dev | prod")

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        description="Async PostgreSQL URL. Format: postgresql+asyncpg://user:pass@host:port/db"
    )
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(description="Redis URL. Format: redis://host:port/db")

    # ── LLM Provider ─────────────────────────────────────────────────────────
    # All LLM config under LLM_* prefix for provider-agnostic naming.
    # To swap provider: change these three env vars only. Zero code changes.
    llm_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenAI-compatible API base URL (OpenRouter, Groq, Together, direct OpenAI)",
    )
    llm_model: str = Field(
        default="qwen/qwen3-6b-plus:free",
        description="Model identifier as expected by the provider",
    )
    llm_api_key: str = Field(description="API key for LLM provider")
    llm_max_rpm: int = Field(default=20, ge=1, description="Max requests per minute to LLM")
    llm_verbose: bool = Field(default=False, description="Enable CrewAI verbose agent logs")

    # ── Docling ───────────────────────────────────────────────────────────────
    docling_use_gpu: bool = Field(default=False)
    docling_device_id: int = Field(default=0, ge=0)
    docling_table_aware: bool = Field(default=True)
    docling_ocr_enabled: bool = Field(default=True)
    docling_extraction_timeout: int = Field(
        default=60, ge=10, description="Docling timeout in seconds"
    )

    # ── Langfuse ──────────────────────────────────────────────────────────────
    langfuse_public_key: str | None = Field(default=None)
    langfuse_secret_key: str | None = Field(default=None)
    langfuse_host: str = Field(default="http://localhost:3000")

    @property
    def langfuse_enabled(self) -> bool:
        """Tracing is enabled only when both keys are present."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    # ── Storage ───────────────────────────────────────────────────────────────
    storage_type: str = Field(default="local", description="local | s3")
    storage_base_path: str = Field(default="./storage")

    # S3/R2 — required only when storage_type == "s3"
    s3_endpoint_url: str | None = Field(default=None)
    s3_access_key: str | None = Field(default=None)
    s3_secret_key: str | None = Field(default=None)
    s3_bucket_name: str = Field(default="resume-matcher")

    # ── Token Budgets ─────────────────────────────────────────────────────────
    token_budget_quick: int = Field(default=8_000, ge=1_000)
    token_budget_standard: int = Field(default=15_000, ge=1_000)
    token_budget_full: int = Field(default=22_000, ge=1_000)

    # ── Timeouts ──────────────────────────────────────────────────────────────
    crew_execution_timeout: int = Field(default=300, ge=30, description="Seconds")

    # ── Limits ────────────────────────────────────────────────────────────────
    max_file_size_mb: int = Field(default=10, ge=1)
    max_batch_size: int = Field(default=200, ge=1)
    rate_limit_per_minute: int = Field(default=30, ge=1)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="DEBUG", description="DEBUG | INFO | WARNING | ERROR")
    log_format: str = Field(default="console", description="console | json")

    # ── Cross-field validation ────────────────────────────────────────────────
    @model_validator(mode="after")
    def validate_s3_config(self) -> "Settings":
        """Require S3 fields when storage_type is s3."""
        if self.storage_type == "s3":
            missing = [
                f for f in ("s3_endpoint_url", "s3_access_key", "s3_secret_key")
                if not getattr(self, f)
            ]
            if missing:
                raise ValueError(
                    f"storage_type=s3 requires: {', '.join(missing).upper()}"
                )
        return self

    @model_validator(mode="after")
    def validate_log_format(self) -> "Settings":
        if self.log_format not in ("console", "json"):
            raise ValueError("LOG_FORMAT must be 'console' or 'json'")
        return self

    @model_validator(mode="after")
    def validate_storage_type(self) -> "Settings":
        if self.storage_type not in ("local", "s3"):
            raise ValueError("STORAGE_TYPE must be 'local' or 's3'")
        return self


# Module-level singleton — import this everywhere.
# Instantiation validates all fields and raises on startup if config is invalid.
settings = Settings()
