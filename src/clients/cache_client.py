"""RedisCacheClient — Redis implementation of BaseCacheClient.

Uses redis.asyncio for non-blocking async operations.
CacheError is non-critical: callers must gracefully degrade on failure.

Connection is created lazily on first use via get_client() to avoid
event loop issues at import time (relevant for Celery worker context).
"""

import json

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from src.core.exceptions.app_exceptions import CacheError
from src.core.logging.logger import get_logger
from src.interfaces.base_cache_client import BaseCacheClient

logger = get_logger(__name__)


class RedisCacheClient(BaseCacheClient):

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        """Lazy init: create connection pool on first use."""
        if self._client is None:
            self._client = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def get(self, key: str) -> str | None:
        """Return cached string value or None on miss. Raises CacheError on connection failure."""
        try:
            value = await self._get_client().get(key)
            if value is None:
                logger.debug("cache_miss", key=key)
            else:
                logger.debug("cache_hit", key=key)
            return value
        except RedisError as exc:
            raise CacheError(f"Redis GET failed: {exc}", {"key": key}) from exc

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Set key with TTL. Raises CacheError on connection failure."""
        try:
            await self._get_client().setex(key, ttl_seconds, value)
            logger.debug("cache_set", key=key, ttl=ttl_seconds)
        except RedisError as exc:
            raise CacheError(f"Redis SET failed: {exc}", {"key": key}) from exc

    async def delete(self, key: str) -> None:
        """Delete key. Raises CacheError on connection failure."""
        try:
            await self._get_client().delete(key)
            logger.debug("cache_deleted", key=key)
        except RedisError as exc:
            raise CacheError(f"Redis DELETE failed: {exc}", {"key": key}) from exc

    async def close(self) -> None:
        """Close Redis connection pool gracefully. Call on app shutdown."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
