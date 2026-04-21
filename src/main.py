"""FastAPI application entry point.

Startup order:
  1. Validate critical config (fail fast if LLM_API_KEY missing)
  2. Setup structured logging
  3. Register middleware (correlation ID)
  4. Register rate limiter
  5. Include routers under /api/v1
  6. Register global exception handlers
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.core.config.settings import settings
from src.core.exceptions.app_exceptions import AppBaseError
from src.core.logging.logger import get_logger, setup_logging
from src.api.middleware.correlation import CorrelationMiddleware
from src.api.routes import (
    batch_routes,
    candidate_routes,
    evaluation_routes,
    health_routes,
    job_routes,
)

# ── Startup validation — fail fast before accepting traffic ───────────────────
def _validate_startup_config() -> None:
    """Raise on startup if required config is missing or invalid."""
    required = {
        "LLM_API_KEY": settings.llm_api_key,
        "DATABASE_URL": settings.database_url,
        "REDIS_URL": settings.redis_url,
    }
    missing = [k for k, v in required.items() if not v or not v.strip()]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Check your .env file."
        )


# ── App lifespan (startup + shutdown) ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _validate_startup_config()
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger = get_logger(__name__)
    logger.info(
        "application_started",
        env=settings.app_env,
        llm_model=settings.llm_model,
        llm_base_url=settings.llm_base_url,
        storage_type=settings.storage_type,
        langfuse_enabled=settings.langfuse_enabled,
    )
    yield
    # Shutdown
    logger.info("application_shutdown")
    # Close Redis connection
    from src.providers.infrastructure import get_cache_client
    cache = get_cache_client()
    if hasattr(cache, "close"):
        await cache.close()


# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Resume Matcher API",
    description="AI-powered CV evaluation backend with CrewAI multi-agent pipeline.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(CorrelationMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(health_routes.router)  # /health — no version prefix
app.include_router(job_routes.router, prefix=API_PREFIX)
app.include_router(evaluation_routes.router, prefix=API_PREFIX)
app.include_router(batch_routes.router, prefix=API_PREFIX)
app.include_router(candidate_routes.router, prefix=API_PREFIX)


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(AppBaseError)
async def app_error_handler(request: Request, exc: AppBaseError) -> JSONResponse:
    """Catch-all for unhandled AppBaseError subtypes not caught in route handlers."""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": type(exc).__name__,
                "message": exc.message,
                "detail": exc.detail,
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler for completely unexpected exceptions."""
    logger = get_logger(__name__)
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_msg=str(exc)[:300],
        path=str(request.url),
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "InternalServerError",
                "message": "An unexpected error occurred.",
                "detail": None,
            },
        },
    )
