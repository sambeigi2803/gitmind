# app/workers/tasks/ingest.py
"""
Repository ingestion task.

This is the Phase 2 skeleton from the roadmap: it establishes the job
lifecycle, status tracking, error handling and retry semantics, with the
chunking/embedding steps stubbed as clearly-marked TODOs so the surface
around them is already production-shaped.

Celery tasks are synchronous, so this uses a separate *sync* SQLAlchemy
session rather than the async one used by FastAPI. Mixing an async
engine into a sync worker is a common source of event-loop errors.
"""

import logging
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.repository import Job, Repository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Sync engine, worker-only. Small pool: each worker process needs just
# enough connections for its own concurrency.
_sync_engine = create_engine(
    str(settings.DATABASE_URL).replace("postgresql://", "postgresql+psycopg://"),
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(bind=_sync_engine, expire_on_commit=False)


def _set_job_status(
    db: Session,
    job: Job,
    status: str,
    *,
    progress: int | None = None,
    error: str | None = None,
) -> None:
    job.status = status
    if progress is not None:
        job.progress = progress
    if error is not None:
        job.error_message = error
    if status == "processing" and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    if status in {"done", "failed"}:
        job.finished_at = datetime.now(timezone.utc)
    db.commit()


@celery_app.task(
    bind=True,
    name="ingest_repository",
    max_retries=3,
    # Exponential backoff with jitter: transient GitHub rate limits and
    # embedding-API 429s are the expected failure mode here.
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def ingest_repository(self: Task, repository_id: str, job_id: str) -> dict:
    """
    Clone, chunk, embed and index a repository.

    Idempotent by design: re-running for the same repository replaces
    its derived data rather than duplicating it, so a retry after a
    partial failure is always safe.
    """
    with SyncSessionLocal() as db:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        repo = db.execute(
            select(Repository).where(Repository.id == repository_id)
        ).scalar_one_or_none()

        if job is None or repo is None:
            # The user disconnected the repo before the worker picked
            # this up. Not an error - just nothing to do.
            logger.info("Skipping ingest; repo or job no longer exists: %s", repository_id)
            return {"status": "skipped", "reason": "repository_or_job_deleted"}

        try:
            _set_job_status(db, job, "processing", progress=0)
            repo.indexingStatus = "processing"
            db.commit()

            # ── Step 1: fetch source ────────────────────────────────
            # TODO(phase-2): download the repo tarball via the GitHub API
            # using the user's decrypted token, extract to a temp dir.
            _set_job_status(db, job, "processing", progress=15)

            # ── Step 2: enumerate + filter files ────────────────────
            # TODO(phase-2): skip binaries, vendored dirs, lockfiles and
            # anything over settings.MAX_FILE_SIZE_KB. Compare each blob
            # SHA against repo_files to skip unchanged files on reindex.
            _set_job_status(db, job, "processing", progress=30)

            # ── Step 3: AST-aware chunking ──────────────────────────
            # TODO(phase-2): tree-sitter split by function/class, falling
            # back to fixed-token windows for unsupported languages.
            _set_job_status(db, job, "processing", progress=50)

            # ── Step 4: embed + persist ─────────────────────────────
            # TODO(phase-2): batch embed chunks, write to code_chunks
            # with pgvector. Delete stale chunks for changed files first.
            _set_job_status(db, job, "processing", progress=80)

            # ── Step 5: repo-level summary ──────────────────────────
            # TODO(phase-3): single LLM pass over the file tree and key
            # entry points; cached for chat context and doc generation.
            _set_job_status(db, job, "processing", progress=95)

            repo.indexingStatus = "done"
            repo.lastIndexedAt = datetime.now(timezone.utc)
            db.commit()
            _set_job_status(db, job, "done", progress=100)

            return {"status": "done", "repository_id": repository_id}

        except Exception as exc:
            logger.exception("Ingestion failed for repository %s", repository_id)

            will_retry = self.request.retries < self.max_retries
            if will_retry:
                # Keep the repo in 'processing' so the UI shows work is
                # still in flight rather than flickering to failed.
                _set_job_status(db, job, "processing", error=str(exc))
                raise self.retry(exc=exc)

            repo.indexingStatus = "failed"
            db.commit()
            _set_job_status(db, job, "failed", error=str(exc))
            return {"status": "failed", "repository_id": repository_id}
