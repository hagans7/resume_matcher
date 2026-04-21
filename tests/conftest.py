
"""Shared pytest fixtures.

Scope hierarchy:
  session  → created once per test run (DB engine, event loop)
  function → created fresh per test (DB session, HTTP client)

Database strategy:
  - Tabel sudah ada dari: alembic upgrade head
  - Repository tests: session per-test, rollback setelah selesai
  - API tests: session per-test, close tanpa rollback (FastAPI commit sendiri)
  - Data dari test bisa tersisa di DB (gunakan ID unik di setiap test)

External dependencies (LLM, Docling, Langfuse) selalu di-mock.
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config.settings import settings
from src.entities.batch import Batch
from src.entities.candidate import Candidate
from src.entities.evaluation_result import (
    EducationMatch,
    EvaluationResult,
    ExperienceMatch,
    SkillMatch,
)
from src.entities.job_requirement import JobRequirement


# ── Test database URL ─────────────────────────────────────────────────────────
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", settings.database_url)


# ── Event loop (session-scoped) ───────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Single event loop untuk seluruh test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── DB engine (session-scoped) ────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Async engine dibuat sekali per session. Tabel sudah ada dari alembic."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    yield engine
    await engine.dispose()


# ── DB session untuk repository tests (rollback setelah test) ─────────────────
@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test session untuk repository tests.

    Menggunakan pola SQLAlchemy 2.x yang benar:
    - async_sessionmaker membuat session baru dari engine
    - session.rollback() dipanggil setelah test selesai
    - Data tidak tersimpan permanen antar test

    CATATAN: Rollback hanya berfungsi jika session belum commit.
    Repository tests tidak commit secara eksplisit, jadi rollback berfungsi.
    API tests (via 'client' fixture) menggunakan session terpisah.
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            # Rollback semua perubahan yang belum di-commit
            await session.rollback()


# ── HTTP client untuk API tests ───────────────────────────────────────────────
@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client untuk API integration tests.

    Menggunakan engine langsung (bukan db_session) karena FastAPI akan
    commit sendiri melalui get_db_session. Tidak perlu rollback di sini —
    koneksi dikelola oleh FastAPI dependency injection.

    Data yang dibuat saat test akan tersimpan di DB. Gunakan UUID yang
    random (sudah dilakukan oleh app) sehingga tidak konflik antar test.
    """
    from src.main import app
    from src.providers.infrastructure import get_db_session

    # Override DB session dengan engine yang sama tapi session terpisah
    api_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_db():
        async with api_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Mock external dependencies ────────────────────────────────────────────────
@pytest.fixture
def mock_extractor():
    from src.entities.extracted_document import ExtractedDocument, Section
    mock = AsyncMock()
    mock.extract.return_value = ExtractedDocument(
        raw_text="Python developer with 3 years experience in FastAPI and PostgreSQL.",
        sections=[Section(heading="Experience", content="FastAPI developer at Acme Corp")],
        page_count=1,
        has_tables=False,
    )
    return mock


@pytest.fixture
def mock_matcher():
    mock = AsyncMock()
    mock.evaluate.return_value = EvaluationResult(
        overall_score=82,
        verdict="shortlist",
        skill_match=SkillMatch(
            score=85, matched=["Python", "FastAPI"], missing=["Docker"], partial=[], notes="Good match"
        ),
        experience_match=ExperienceMatch(score=80, relevant_years=3, required_years=2, notes="Meets requirement"),
        education_match=EducationMatch(score=75, meets_requirement=True, notes="Relevant degree"),
        red_flags=[],
        summary="Strong candidate with good Python background.",
        token_used=1500,
        processing_ms=3200,
        crew_version="1.0.0",
        llm_model="qwen/qwen3-6b-plus:free",
    )
    return mock


@pytest.fixture
def mock_storage():
    mock = AsyncMock()
    mock.save.return_value = "cv/original/test-id.pdf"
    mock.load.return_value = b"%PDF-1.4 fake pdf content"
    mock.exists.return_value = True
    return mock


@pytest.fixture
def mock_cache():
    mock = AsyncMock()
    mock.get.return_value = None
    mock.set.return_value = None
    return mock


@pytest.fixture
def mock_tracer():
    mock = MagicMock()
    mock.start_trace.return_value = MagicMock()
    mock.end_trace.return_value = None
    mock.log_error.return_value = None
    return mock


# ── Entity factories ──────────────────────────────────────────────────────────
@pytest.fixture
def sample_job() -> JobRequirement:
    return JobRequirement(
        id="job-test-001",
        title="Senior Python Developer",
        description=(
            "We are looking for a Python developer with FastAPI experience. "
            "Required: Python, FastAPI, PostgreSQL. "
            "Preferred: Docker, Kubernetes. Min 2 years experience."
        ),
        evaluation_mode="standard",
        status="active",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_candidate(sample_job: JobRequirement) -> Candidate:
    return Candidate(
        id="cand-test-001",
        job_id=sample_job.id,
        file_key="cv/original/cand-test-001.pdf",
        file_hash="abc123" * 10,
        original_filename="john_doe_cv.pdf",
        status="evaluated",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        score=82,
        verdict="shortlist",
    )


@pytest.fixture
def sample_batch(sample_job: JobRequirement) -> Batch:
    return Batch(
        id="batch-test-001",
        job_id=sample_job.id,
        total=5,
        succeeded=3,
        failed=1,
        status="processing",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nPython developer CV"