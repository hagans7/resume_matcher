"""BaseDocumentExtractor ABC.

Abstracts document text extraction (Docling v1).
Returns a structured ExtractedDocument entity — not raw text.
"""

from abc import ABC, abstractmethod

from src.entities.extracted_document import ExtractedDocument


class BaseDocumentExtractor(ABC):

    @abstractmethod
    async def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocument:
        """Extract structured text from PDF or DOCX bytes. Raises DocumentExtractionError."""
