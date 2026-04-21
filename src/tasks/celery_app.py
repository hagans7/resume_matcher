"""Celery application instance.

Configuration rationale:
- task_acks_late=True       → task stays in queue until fully complete;
                              if worker crashes, task is re-queued (not lost)
- worker_prefetch_multiplier=1 → worker takes one task at a time (fair dispatch)
- worker_concurrency=1      → one concurrent task per worker process;
                              Docling model loading is 1-2GB RAM — concurrent
                              tasks would risk OOM. Scale via more worker processes.
- task_time_limit=600       → hard kill after 10 min (prevents zombie tasks)
- task_soft_time_limit=300  → raises SoftTimeLimitExceeded after 5 min (graceful)
"""

from celery import Celery

from src.core.config.settings import settings

celery_app = Celery(
    "resume_matcher",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=1,
    # Timeouts
    task_time_limit=600,
    task_soft_time_limit=settings.crew_execution_timeout,
    # Results
    result_expires=86400,       # keep results 24h
    # Auto-discovery of task modules
    include=[
        "src.tasks.evaluate_single_task",
        "src.tasks.process_batch_task",
    ],
)
