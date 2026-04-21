"""Health check endpoint.

Checks liveness of critical dependencies: DB and Redis.
Returns 200 if all healthy, 503 if any critical dependency is down.
"""

from fastapi import APIRouter
from sqlalchemy import text

from src.core.logging.logger import get_logger
from src.providers.infrastructure import _engine, get_cache_client

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    """Return health status of DB and Redis. Used by Docker healthcheck and load balancers."""
    status = {"db": "unknown", "redis": "unknown"}
    healthy = True

    # Check PostgreSQL
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["db"] = "ok"
    except Exception as exc:
        status["db"] = f"error: {str(exc)[:80]}"
        healthy = False
        logger.error("health_check_db_failed", error=str(exc))

    # Check Redis
    try:
        cache = get_cache_client()
        await cache.set("__health__", "1", ttl_seconds=5)
        val = await cache.get("__health__")
        status["redis"] = "ok" if val == "1" else "error: unexpected value"
    except Exception as exc:
        status["redis"] = f"error: {str(exc)[:80]}"
        healthy = False
        logger.error("health_check_redis_failed", error=str(exc))

    http_status = 200 if healthy else 503
    return {"status": "ok" if healthy else "degraded", **status}
