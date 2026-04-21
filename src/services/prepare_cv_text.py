"""PrepareCVTextService — extracts text via Docling, masks PII, stores parsed text.

Extracted from original god-service per blueprint v2 revision.
Single responsibility: turn raw file bytes into clean, masked text string.

Steps:
  1. Extract text via Docling (BaseDocumentExtractor)
  2. Validate extraction produced usable content
  3. Store parsed text to storage (cv/parsed/{id}.txt)
  4. Mask PII (email, phone, NIK, URLs)
  5. Return masked text string
"""

from src.core.exceptions.app_exceptions import DocumentExtractionError
from src.core.logging.logger import get_logger
from src.interfaces.base_document_extractor import BaseDocumentExtractor
from src.interfaces.base_storage_client import BaseStorageClient
from src.services.mask_pii import MaskPIIService

logger = get_logger(__name__)


class PrepareCVTextService:

    def __init__(
        self,
        extractor: BaseDocumentExtractor,
        storage: BaseStorageClient,
        pii_masker: MaskPIIService,
    ) -> None:
        self._extractor = extractor
        self._storage = storage
        self._pii_masker = pii_masker

    async def execute(
        self,
        file_bytes: bytes,
        filename: str,
        candidate_id: str,
    ) -> str:
        """Extract, store, and mask CV text. Returns masked text for LLM.

        Raises: DocumentExtractionError, StorageError.
        """
        # 1. Extract text via Docling
        extracted = await self._extractor.extract(file_bytes, filename)

        # 2. Validate content quality
        if not extracted.has_content():
            raise DocumentExtractionError(
                f"CV extraction produced no usable text: {filename}",
                {"candidate_id": candidate_id, "filename": filename},
            )

        logger.info(
            "cv_extracted",
            candidate_id=candidate_id,
            pages=extracted.page_count,
            chars=extracted.text_length(),
            sections=len(extracted.sections),
        )

        # 3. Store raw parsed text (before masking) for audit trail
        parsed_key = f"cv/parsed/{candidate_id}.txt"
        await self._storage.save(
            key=parsed_key,
            data=extracted.raw_text.encode("utf-8"),
            content_type="text/plain",
        )

        # 4. Mask PII before returning to caller
        masked_text = self._pii_masker.execute(extracted.raw_text)

        logger.info(
            "cv_text_prepared",
            candidate_id=candidate_id,
            original_chars=extracted.text_length(),
            masked_chars=len(masked_text),
        )
        return masked_text
