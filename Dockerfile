# ── Base Image ────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# UV_SYSTEM_PYTHON=1 → install packages directly into /usr/local/lib/python3.12
# No virtualenv created. uvicorn, celery, etc. go to /usr/local/bin/ (already in PATH).
# This is the correct pattern for Docker: container = isolation boundary.
ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# ── Install Dependencies ──────────────────────────────────────────────────────
# Copy only dependency manifest first for Docker layer caching.
# Re-runs only when pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock* ./

# Install all production dependencies from pyproject.toml into system Python
RUN uv pip install --system --no-dev -e . 2>/dev/null || \
    uv pip install --system \
    "fastapi>=0.115.0,<0.116.0" \
    "uvicorn[standard]>=0.32.0,<0.33.0" \
    "python-multipart>=0.0.12,<0.1.0" \
    "pydantic>=2.10.0,<3.0.0" \
    "pydantic-settings>=2.6.0,<3.0.0" \
    "sqlalchemy[asyncio]>=2.0.36,<2.1.0" \
    "asyncpg>=0.30.0,<0.31.0" \
    "alembic>=1.14.0,<2.0.0" \
    "celery[redis]>=5.4.0,<5.5.0" \
    "redis>=5.2.0,<6.0.0" \
    "aiofiles>=24.1.0,<25.0.0" \
    "httpx>=0.28.0,<0.29.0" \
    "crewai>=0.100.0,<0.120.0" \
    "crewai-tools>=0.17.0,<0.25.0" \
    "docling>=2.20.0,<3.0.0" \
    "langfuse>=2.50.0,<3.0.0" \
    "structlog>=24.4.0,<25.0.0" \
    "rich>=13.9.0,<14.0.0" \
    "slowapi>=0.1.9,<0.2.0"

# ── Copy Application Code ─────────────────────────────────────────────────────
# Copy AFTER pip install so code changes don't invalidate the dep cache layer
COPY . .

# Ensure runtime directories exist inside container
RUN mkdir -p storage/cv/original storage/cv/parsed storage/reports logs

# ── Security: non-root user ───────────────────────────────────────────────────
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# uvicorn and celery are now in /usr/local/bin/ — no PATH games needed
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
