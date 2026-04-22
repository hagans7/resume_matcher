# 🧠 Resume Matcher

> AI-powered CV evaluation backend — match candidates to job descriptions automatically.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9?style=flat-square)

Resume Matcher is a backend service that uses LLMs to evaluate and rank CVs against job descriptions. Built with FastAPI, Celery for async processing, and CrewAI for multi-agent orchestration.

---

## 🔧 Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| uv | latest |
| Docker + Docker Compose | 24+ / 2.x |

**Install uv:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 🚀 Quick Setup

### 1. Clone & install dependencies

```bash
git clone <repo-url> resume_matcher
cd resume_matcher

uv venv --python 3.12
source .venv/bin/activate       # Windows: .venv\Scripts\Activate.ps1

uv sync --extra dev
```

### 2. Configure environment

```bash
cp .env.example .env
```

Minimum required values in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://matcher:matcherpass@localhost:5432/resume_matcher
REDIS_URL=redis://localhost:6379/0
LLM_API_KEY=sk-or-...        # Get a free key at openrouter.ai
LLM_MODEL=qwen/qwen3-6b-plus:free
```

> **Free LLM**: Sign up at [openrouter.ai](https://openrouter.ai), create an API key, and use the `qwen/qwen3-6b-plus:free` model.

### 3. Start infrastructure

```bash
docker compose up -d db redis
docker compose ps   # wait until both show "healthy"
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the app

Open two terminals:

```bash
# Terminal 1 — API server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Celery worker
celery -A src.tasks.celery_app worker --loglevel=info --concurrency=1
```

API docs available at: **http://localhost:8000/docs**

---

## 🐳 Full Docker Setup

To run everything in containers:

```bash
uv lock                              # generate lockfile first (commit this)
docker compose build
docker compose up -d
docker compose exec app alembic upgrade head
```

Optional — enable [Langfuse](https://langfuse.com) for LLM tracing:

```bash
docker compose --profile langfuse up -d
# UI at http://localhost:3000
```

---

## 🧪 Testing

```bash
# Run tests
pytest

# Check API health
curl http://localhost:8000/health
# Expected: {"status": "ok", "db": "ok", "redis": "ok"}
```

---

## 🛑 Shutdown

```bash
# Stop services (keeps DB data)
docker compose down

# Stop + wipe DB volumes
docker compose down -v
```

---

## 📁 Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI |
| Task Queue | Celery + Redis |
| Database | PostgreSQL (asyncpg) |
| AI Agents | CrewAI |
| Document Parsing | Docling |
| LLM Observability | Langfuse |
| Migrations | Alembic |