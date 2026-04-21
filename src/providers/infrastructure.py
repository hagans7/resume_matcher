# """Infrastructure providers — singleton clients and DB session factory.

# lru_cache(maxsize=1) creates a singleton per process.
# DB session is per-request via async generator (FastAPI Depends pattern).

# Celery workers must NOT use FastAPI Depends — they instantiate manually.
# See tasks/evaluate_single_task.py for worker-side instantiation pattern.
# """

# from functools import lru_cache

# from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# from src.core.config.settings import settings
# from src.clients.cache_client import RedisCacheClient
# from src.clients.document_extractor import DoclingExtractorClient
# from src.clients.resume_matcher import CrewAIResumeMatcherClient
# from src.clients.storage_client import LocalStorageClient
# from src.clients.tracer_client import LangfuseTracerClient
# from src.interfaces.base_cache_client import BaseCacheClient
# from src.interfaces.base_document_extractor import BaseDocumentExtractor
# from src.interfaces.base_resume_matcher import BaseResumeMatcher
# from src.interfaces.base_storage_client import BaseStorageClient
# from src.interfaces.base_tracer_client import BaseTracerClient

# # ── DB Engine (module-level, shared across requests) ─────────────────────────
# _engine = create_async_engine(
#     settings.database_url,
#     pool_size=settings.db_pool_size,
#     max_overflow=settings.db_max_overflow,
#     echo=False,
# )
# _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


# async def get_db_session():
#     """Async generator: yields one AsyncSession per request. Auto-commits on exit."""
#     async with _session_factory() as session:
#         async with session.begin():
#             yield session


# # ── Singleton Infrastructure Clients ─────────────────────────────────────────

# @lru_cache(maxsize=1)
# def get_storage_client() -> BaseStorageClient:
#     return LocalStorageClient(base_path=settings.storage_base_path)


# @lru_cache(maxsize=1)
# def get_cache_client() -> BaseCacheClient:
#     return RedisCacheClient(redis_url=settings.redis_url)


# @lru_cache(maxsize=1)
# def get_tracer_client() -> BaseTracerClient:
#     return LangfuseTracerClient(
#         public_key=settings.langfuse_public_key,
#         secret_key=settings.langfuse_secret_key,
#         host=settings.langfuse_host,
#     )


# @lru_cache(maxsize=1)
# def get_document_extractor() -> BaseDocumentExtractor:
#     return DoclingExtractorClient(
#         use_gpu=settings.docling_use_gpu,
#         device_id=settings.docling_device_id,
#         table_aware=settings.docling_table_aware,
#         ocr_enabled=settings.docling_ocr_enabled,
#         extraction_timeout=settings.docling_extraction_timeout,
#         max_file_size_mb=settings.max_file_size_mb,
#     )


# @lru_cache(maxsize=1)
# def get_resume_matcher() -> BaseResumeMatcher:
#     return CrewAIResumeMatcherClient(
#         llm_model=settings.llm_model,
#         llm_api_key=settings.llm_api_key,
#         llm_base_url=settings.llm_base_url,
#         llm_max_rpm=settings.llm_max_rpm,
#         llm_verbose=settings.llm_verbose,
#         crew_execution_timeout=settings.crew_execution_timeout,
#         tracer=get_tracer_client(),
#     )


"""Infrastructure providers — singleton clients and DB session factory.

lru_cache(maxsize=1) creates a singleton per process.
DB session is per-request via async generator (FastAPI Depends pattern).

Celery workers must NOT use FastAPI Depends — they instantiate manually.
See tasks/evaluate_single_task.py for worker-side instantiation pattern.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config.settings import settings
from src.clients.cache_client import RedisCacheClient
from src.clients.document_extractor import DoclingExtractorClient
from src.clients.resume_matcher import CrewAIResumeMatcherClient
from src.clients.storage_client import LocalStorageClient
from src.clients.tracer_client import LangfuseTracerClient
from src.interfaces.base_cache_client import BaseCacheClient
from src.interfaces.base_document_extractor import BaseDocumentExtractor
from src.interfaces.base_resume_matcher import BaseResumeMatcher
from src.interfaces.base_storage_client import BaseStorageClient
from src.interfaces.base_tracer_client import BaseTracerClient

# ── DB Engine (module-level, shared across requests) ─────────────────────────
_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    echo=False,
)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db_session():
    """Async generator: yields one AsyncSession per request.

    SQLAlchemy 2.x async_sessionmaker uses autobegin=True by default.
    The session automatically starts a transaction on first DB operation
    and commits/rolls back when the context manager exits.
    Do NOT call session.begin() explicitly — it conflicts with autobegin.
    """
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Singleton Infrastructure Clients ─────────────────────────────────────────

@lru_cache(maxsize=1)
def get_storage_client() -> BaseStorageClient:
    return LocalStorageClient(base_path=settings.storage_base_path)


@lru_cache(maxsize=1)
def get_cache_client() -> BaseCacheClient:
    return RedisCacheClient(redis_url=settings.redis_url)


@lru_cache(maxsize=1)
def get_tracer_client() -> BaseTracerClient:
    return LangfuseTracerClient(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


@lru_cache(maxsize=1)
def get_document_extractor() -> BaseDocumentExtractor:
    return DoclingExtractorClient(
        use_gpu=settings.docling_use_gpu,
        device_id=settings.docling_device_id,
        table_aware=settings.docling_table_aware,
        ocr_enabled=settings.docling_ocr_enabled,
        extraction_timeout=settings.docling_extraction_timeout,
        max_file_size_mb=settings.max_file_size_mb,
    )


@lru_cache(maxsize=1)
def get_resume_matcher() -> BaseResumeMatcher:
    return CrewAIResumeMatcherClient(
        llm_model=settings.llm_model,
        llm_api_key=settings.llm_api_key,
        llm_base_url=settings.llm_base_url,
        llm_max_rpm=settings.llm_max_rpm,
        llm_verbose=settings.llm_verbose,
        crew_execution_timeout=settings.crew_execution_timeout,
        tracer=get_tracer_client(),
    )