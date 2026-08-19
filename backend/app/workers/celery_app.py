# app/workers/celery_app.py
"""
Celery application.

Run a worker with:
    celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

Ingestion is IO- and API-heavy rather than CPU-heavy, so a modest
concurrency with prefetch disabled gives fairer distribution of long
tasks across workers.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "gitmind",
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND),
    include=["app.workers.tasks.ingest"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Don't let a worker hoard queued tasks - ingestion runtimes vary
    # widely, so prefetching causes long tail latency.
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Hard ceiling so a pathological repo can't occupy a worker forever.
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    result_expires=60 * 60 * 24,
)
