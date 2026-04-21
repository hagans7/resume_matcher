"""LocalStorageClient — local filesystem implementation of BaseStorageClient.

v1: local filesystem under STORAGE_BASE_PATH.
v2 upgrade path: implement S3StorageClient(BaseStorageClient), wire in providers/infrastructure.py.
Zero code changes needed outside this file and providers.

Key layout:
  cv/original/{candidate_id}.{ext}   ← raw uploaded file
  cv/parsed/{candidate_id}.txt       ← Docling extracted text
  reports/{candidate_id}.md          ← evaluation report
"""

import aiofiles
import aiofiles.os
from pathlib import Path

from src.core.exceptions.app_exceptions import NotFoundError, StorageError
from src.core.logging.logger import get_logger
from src.interfaces.base_storage_client import BaseStorageClient

logger = get_logger(__name__)


class LocalStorageClient(BaseStorageClient):

    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Save bytes to local filesystem. Creates parent dirs as needed. Raises StorageError."""
        full_path = self._base / key
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(data)
            logger.debug("storage_saved", key=key, bytes=len(data))
            return key
        except OSError as exc:
            raise StorageError(f"Failed to save file: {exc}", {"key": key}) from exc

    async def load(self, key: str) -> bytes:
        """Load bytes from local filesystem. Raises StorageError, NotFoundError."""
        full_path = self._base / key
        if not full_path.exists():
            raise NotFoundError(f"File not found in storage: {key}", {"key": key})
        try:
            async with aiofiles.open(full_path, "rb") as f:
                data = await f.read()
            logger.debug("storage_loaded", key=key, bytes=len(data))
            return data
        except OSError as exc:
            raise StorageError(f"Failed to load file: {exc}", {"key": key}) from exc

    async def delete(self, key: str) -> None:
        """Delete file. Raises StorageError."""
        full_path = self._base / key
        try:
            await aiofiles.os.remove(full_path)
            logger.debug("storage_deleted", key=key)
        except FileNotFoundError:
            pass  # idempotent delete
        except OSError as exc:
            raise StorageError(f"Failed to delete file: {exc}", {"key": key}) from exc

    async def exists(self, key: str) -> bool:
        """Return True if key exists."""
        return (self._base / key).exists()
