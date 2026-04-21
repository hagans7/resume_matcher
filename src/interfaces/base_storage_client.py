"""BaseStorageClient ABC.

Abstracts file storage (local filesystem v1, S3/R2 v2).
To swap storage backend: implement this ABC, wire in providers/infrastructure.py.
"""

from abc import ABC, abstractmethod


class BaseStorageClient(ABC):

    @abstractmethod
    async def save(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Save bytes to storage under key. Return the key. Raises StorageError."""

    @abstractmethod
    async def load(self, key: str) -> bytes:
        """Load bytes by key. Raises StorageError, NotFoundError."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete file at key. Raises StorageError."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if key exists in storage."""
