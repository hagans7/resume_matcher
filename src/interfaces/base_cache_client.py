"""BaseCacheClient ABC.

Abstracts Redis cache operations.
CacheError is non-critical — callers must gracefully degrade on failure.
"""

from abc import ABC, abstractmethod


class BaseCacheClient(ABC):

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Return cached value or None on miss. Raises CacheError on connection failure."""

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Set key with TTL. Raises CacheError on connection failure."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key. Raises CacheError on connection failure."""
