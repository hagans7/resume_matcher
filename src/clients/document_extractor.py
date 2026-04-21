# """DoclingExtractorClient — Docling implementation of BaseDocumentExtractor.

# Docling pipeline is lazy-loaded on first call (not at __init__) to avoid
# GPU memory allocation until actually needed, and to keep startup time fast.

# Supports PDF and DOCX. File is written to a temp file, processed, then deleted.
# Timeout is enforced via asyncio.wait_for wrapping the sync call in executor.

# Extraction lifecycle:
#   file_bytes + filename
#     → validate size + extension
#     → write temp file
#     → Docling DocumentConverter.convert()
#     → parse result → ExtractedDocument entity
#     → delete temp file
#     → return entity
# """

# import asyncio
# import os
# import tempfile
# from pathlib import Path

# from src.core.constants.app_constants import ALLOWED_FILE_EXTENSIONS
# from src.core.exceptions.app_exceptions import (
#     DocumentExtractionError,
#     FileValidationError,
#     FileTooLargeError,
# )
# from src.core.logging.logger import get_logger
# from src.entities.extracted_document import ExtractedDocument, Section
# from src.interfaces.base_document_extractor import BaseDocumentExtractor

# logger = get_logger(__name__)


# class DoclingExtractorClient(BaseDocumentExtractor):

#     def __init__(
#         self,
#         use_gpu: bool,
#         device_id: int,
#         table_aware: bool,
#         ocr_enabled: bool,
#         extraction_timeout: int,
#         max_file_size_mb: int,
#     ) -> None:
#         self._use_gpu = use_gpu
#         self._device_id = device_id
#         self._table_aware = table_aware
#         self._ocr_enabled = ocr_enabled
#         self._timeout = extraction_timeout
#         self._max_bytes = max_file_size_mb * 1024 * 1024
#         self._converter = None  # lazy-loaded

#     def _get_converter(self):
#         """Lazy-load Docling DocumentConverter. Called on first extract()."""
#         if self._converter is not None:
#             return self._converter

#         try:
#             from docling.document_converter import DocumentConverter
#             from docling.datamodel.pipeline_options import PipelineOptions
#             from docling.datamodel.base_models import InputFormat

#             pipeline_options = PipelineOptions()
#             pipeline_options.do_ocr = self._ocr_enabled
#             pipeline_options.do_table_structure = self._table_aware

#             self._converter = DocumentConverter()
#             logger.info(
#                 "docling_converter_initialized",
#                 use_gpu=self._use_gpu,
#                 ocr=self._ocr_enabled,
#                 table_aware=self._table_aware,
#             )
#             return self._converter
#         except ImportError as exc:
#             raise DocumentExtractionError(
#                 "Docling not installed. Run: uv sync"
#             ) from exc
#         except Exception as exc:
#             raise DocumentExtractionError(
#                 f"Failed to initialize Docling converter: {exc}"
#             ) from exc

#     def _validate(self, file_bytes: bytes, filename: str) -> None:
#         """Validate file size and extension. Raises FileValidationError, FileTooLargeError."""
#         if len(file_bytes) > self._max_bytes:
#             raise FileTooLargeError(
#                 f"File exceeds {self._max_bytes // (1024*1024)}MB limit",
#                 {"filename": filename, "size_bytes": len(file_bytes)},
#             )
#         ext = Path(filename).suffix.lower()
#         if ext not in ALLOWED_FILE_EXTENSIONS:
#             raise FileValidationError(
#                 f"Unsupported file type: {ext}. Allowed: {ALLOWED_FILE_EXTENSIONS}",
#                 {"filename": filename},
#             )

#     def _run_extraction(self, temp_path: str) -> ExtractedDocument:
#         """Synchronous Docling extraction. Runs in executor to avoid blocking event loop."""
#         try:
#             converter = self._get_converter()
#             result = converter.convert(temp_path)
#             doc = result.document

#             # Full text
#             raw_text = doc.export_to_text()

#             # Structured sections: iterate document elements
#             sections: list[Section] = []
#             current_heading = ""
#             current_content_parts: list[str] = []

#             for element, _level in doc.iterate_items():
#                 el_type = type(element).__name__

#                 if el_type in ("SectionHeaderItem", "TitleItem"):
#                     # Flush previous section
#                     if current_content_parts:
#                         sections.append(Section(
#                             heading=current_heading,
#                             content=" ".join(current_content_parts).strip(),
#                         ))
#                         current_content_parts = []
#                     current_heading = element.text if hasattr(element, "text") else ""

#                 elif el_type == "TextItem":
#                     text = element.text if hasattr(element, "text") else ""
#                     if text.strip():
#                         current_content_parts.append(text.strip())

#             # Flush last section
#             if current_content_parts:
#                 sections.append(Section(
#                     heading=current_heading,
#                     content=" ".join(current_content_parts).strip(),
#                 ))

#             # Page count and table detection
#             page_count = len(result.pages) if hasattr(result, "pages") else 1
#             has_tables = any(
#                 type(el).__name__ == "TableItem"
#                 for el, _ in doc.iterate_items()
#             )

#             return ExtractedDocument(
#                 raw_text=raw_text,
#                 sections=sections,
#                 page_count=page_count,
#                 has_tables=has_tables,
#             )

#         except Exception as exc:
#             raise DocumentExtractionError(
#                 f"Docling extraction failed: {exc}",
#                 {"error": str(exc)},
#             ) from exc

#     async def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocument:
#         """Extract structured text from PDF or DOCX. Raises DocumentExtractionError."""
#         self._validate(file_bytes, filename)

#         ext = Path(filename).suffix.lower()
#         # Fix 4: initialize tmp_path to None so finally block never raises NameError
#         # even if NamedTemporaryFile fails before tmp_path = tmp.name is reached.
#         tmp_path = None

#         try:
#             # Write bytes to temp file (Docling requires file path, not bytes)
#             with tempfile.NamedTemporaryFile(
#                 suffix=ext, delete=False
#             ) as tmp:
#                 tmp.write(file_bytes)
#                 tmp_path = tmp.name

#             logger.info(
#                 "docling_extraction_started",
#                 filename=filename,
#                 size_bytes=len(file_bytes),
#             )

#             # Run sync Docling in thread executor to avoid blocking event loop
#             loop = asyncio.get_event_loop()
#             extracted = await asyncio.wait_for(
#                 loop.run_in_executor(None, self._run_extraction, tmp_path),
#                 timeout=self._timeout,
#             )

#             if not extracted.has_content():
#                 raise DocumentExtractionError(
#                     "Extraction produced no usable text",
#                     {"filename": filename},
#                 )

#             logger.info(
#                 "docling_extraction_complete",
#                 filename=filename,
#                 pages=extracted.page_count,
#                 sections=len(extracted.sections),
#                 chars=extracted.text_length(),
#                 has_tables=extracted.has_tables,
#             )
#             return extracted

#         except asyncio.TimeoutError:
#             raise DocumentExtractionError(
#                 f"Docling extraction timed out after {self._timeout}s",
#                 {"filename": filename},
#             )
#         except (FileValidationError, FileTooLargeError, DocumentExtractionError):
#             raise
#         except Exception as exc:
#             raise DocumentExtractionError(
#                 f"Unexpected extraction error: {exc}",
#                 {"filename": filename},
#             ) from exc
#         finally:
#             # Always clean up temp file
#             if tmp_path and os.path.exists(tmp_path):
#                 try:
#                     os.unlink(tmp_path)
#                 except OSError:
#                     pass


"""DoclingExtractorClient — Docling implementation of BaseDocumentExtractor.

Docling pipeline is lazy-loaded on first call (not at __init__) to avoid
GPU memory allocation until actually needed, and to keep startup time fast.

Supports PDF and DOCX. File is written to a temp file, processed, then deleted.
Timeout is enforced via asyncio.wait_for wrapping the sync call in executor.

Extraction lifecycle:
  file_bytes + filename
    → validate size + extension
    → write temp file
    → Docling DocumentConverter.convert()
    → parse result → ExtractedDocument entity
    → delete temp file
    → return entity
"""

import asyncio
import os
import tempfile
from pathlib import Path

from src.core.constants.app_constants import ALLOWED_FILE_EXTENSIONS
from src.core.exceptions.app_exceptions import (
    DocumentExtractionError,
    FileValidationError,
    FileTooLargeError,
)
from src.core.logging.logger import get_logger
from src.entities.extracted_document import ExtractedDocument, Section
from src.interfaces.base_document_extractor import BaseDocumentExtractor

logger = get_logger(__name__)


class DoclingExtractorClient(BaseDocumentExtractor):

    def __init__(
        self,
        use_gpu: bool,
        device_id: int,
        table_aware: bool,
        ocr_enabled: bool,
        extraction_timeout: int,
        max_file_size_mb: int,
    ) -> None:
        self._use_gpu = use_gpu
        self._device_id = device_id
        self._table_aware = table_aware
        self._ocr_enabled = ocr_enabled
        self._timeout = extraction_timeout
        self._max_bytes = max_file_size_mb * 1024 * 1024
        self._converter = None  # lazy-loaded

    # def _get_converter(self):
    #     """Lazy-load Docling DocumentConverter. Called on first extract()."""
    #     if self._converter is not None:
    #         return self._converter

    #     try:
    #         from docling.document_converter import DocumentConverter

    #         # Docling 2.x changed API: PipelineOptions → PdfPipelineOptions.
    #         # Try new API first, fall back to plain DocumentConverter if import fails.
    #         try:
    #             from docling.datamodel.pipeline_options import PdfPipelineOptions
    #             from docling.document_converter import PdfFormatOption
    #             pipeline_options = PdfPipelineOptions()
    #             pipeline_options.do_ocr = self._ocr_enabled
    #             pipeline_options.do_table_structure = self._table_aware
    #             self._converter = DocumentConverter(
    #                 format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
    #             )
    #         except (ImportError, TypeError, AttributeError, Exception):
    #             # Fallback: plain DocumentConverter — works with any Docling version
    #             self._converter = DocumentConverter()

    #         logger.info(
    #             "docling_converter_initialized",
    #             use_gpu=self._use_gpu,
    #             ocr=self._ocr_enabled,
    #             table_aware=self._table_aware,
    #         )
    #         return self._converter
    #     except ImportError as exc:
    #         raise DocumentExtractionError(
    #             "Docling not installed. Run: uv sync"
    #         ) from exc
    #     except Exception as exc:
    #         raise DocumentExtractionError(
    #             f"Failed to initialize Docling converter: {exc}"
    #         ) from excdef _get_converter(self):
    def _get_converter(self):
        """Lazy-load Docling DocumentConverter. Called on first extract()."""
        if self._converter is not None:
            return self._converter

        try:
            from docling.document_converter import DocumentConverter

            try:
                from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
                from docling.document_converter import PdfFormatOption
                
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = self._ocr_enabled
                pipeline_options.do_table_structure = self._table_aware
                
                if self._ocr_enabled:
                    pipeline_options.ocr_options = RapidOcrOptions()

                self._converter = DocumentConverter(
                    format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
                )
            except (ImportError, TypeError, AttributeError, Exception) as inner_exc:
                logger.warning(f"Failed to use new Docling API, falling back to default: {inner_exc}")
                # Fallback: plain DocumentConverter
                self._converter = DocumentConverter()

            logger.info(
                "docling_converter_initialized",
                use_gpu=self._use_gpu,
                ocr=self._ocr_enabled,
                table_aware=self._table_aware,
                engine="RapidOCR"
            )
            return self._converter
        except ImportError as exc:
            raise DocumentExtractionError(
                "Docling not installed. Run: uv sync"
            ) from exc
        except Exception as exc:
            raise DocumentExtractionError(
                f"Failed to initialize Docling converter: {exc}"
            ) from exc
            
    def _validate(self, file_bytes: bytes, filename: str) -> None:
        """Validate file size and extension. Raises FileValidationError, FileTooLargeError."""
        if len(file_bytes) > self._max_bytes:
            raise FileTooLargeError(
                f"File exceeds {self._max_bytes // (1024*1024)}MB limit",
                {"filename": filename, "size_bytes": len(file_bytes)},
            )
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_FILE_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported file type: {ext}. Allowed: {ALLOWED_FILE_EXTENSIONS}",
                {"filename": filename},
            )

    def _run_extraction(self, temp_path: str) -> ExtractedDocument:
        """Synchronous Docling extraction. Runs in executor to avoid blocking event loop."""
        try:
            converter = self._get_converter()
            result = converter.convert(temp_path)
            doc = result.document

            # Full text
            raw_text = doc.export_to_text()

            # Structured sections: iterate document elements
            sections: list[Section] = []
            current_heading = ""
            current_content_parts: list[str] = []

            for element, _level in doc.iterate_items():
                el_type = type(element).__name__

                if el_type in ("SectionHeaderItem", "TitleItem"):
                    # Flush previous section
                    if current_content_parts:
                        sections.append(Section(
                            heading=current_heading,
                            content=" ".join(current_content_parts).strip(),
                        ))
                        current_content_parts = []
                    current_heading = element.text if hasattr(element, "text") else ""

                elif el_type == "TextItem":
                    text = element.text if hasattr(element, "text") else ""
                    if text.strip():
                        current_content_parts.append(text.strip())

            # Flush last section
            if current_content_parts:
                sections.append(Section(
                    heading=current_heading,
                    content=" ".join(current_content_parts).strip(),
                ))

            # Page count and table detection
            page_count = len(result.pages) if hasattr(result, "pages") else 1
            has_tables = any(
                type(el).__name__ == "TableItem"
                for el, _ in doc.iterate_items()
            )

            return ExtractedDocument(
                raw_text=raw_text,
                sections=sections,
                page_count=page_count,
                has_tables=has_tables,
            )

        except Exception as exc:
            raise DocumentExtractionError(
                f"Docling extraction failed: {exc}",
                {"error": str(exc)},
            ) from exc

    async def extract(self, file_bytes: bytes, filename: str) -> ExtractedDocument:
        """Extract structured text from PDF or DOCX. Raises DocumentExtractionError."""
        self._validate(file_bytes, filename)

        ext = Path(filename).suffix.lower()
        # Fix 4: initialize tmp_path to None so finally block never raises NameError
        # even if NamedTemporaryFile fails before tmp_path = tmp.name is reached.
        tmp_path = None

        try:
            # Write bytes to temp file (Docling requires file path, not bytes)
            with tempfile.NamedTemporaryFile(
                suffix=ext, delete=False
            ) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            logger.info(
                "docling_extraction_started",
                filename=filename,
                size_bytes=len(file_bytes),
            )

            # Run sync Docling in thread executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            extracted = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_extraction, tmp_path),
                timeout=self._timeout,
            )

            if not extracted.has_content():
                raise DocumentExtractionError(
                    "Extraction produced no usable text",
                    {"filename": filename},
                )

            logger.info(
                "docling_extraction_complete",
                filename=filename,
                pages=extracted.page_count,
                sections=len(extracted.sections),
                chars=extracted.text_length(),
                has_tables=extracted.has_tables,
            )
            return extracted

        except asyncio.TimeoutError:
            raise DocumentExtractionError(
                f"Docling extraction timed out after {self._timeout}s",
                {"filename": filename},
            )
        except (FileValidationError, FileTooLargeError, DocumentExtractionError):
            raise
        except Exception as exc:
            raise DocumentExtractionError(
                f"Unexpected extraction error: {exc}",
                {"filename": filename},
            ) from exc
        finally:
            # Always clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass