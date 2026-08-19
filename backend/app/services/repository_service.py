# app/services/repository_service.py
"""
Business logic for connecting and managing repositories.

Every function that touches a repository takes `user_id` and verifies
ownership itself. Authorization is enforced here, not in the route
layer, so it can't be bypassed by a new endpoint forgetting the check.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PlanLimitExceededError,
    RepositoryTooLargeError,
)
from app.models.repository import Job, Repository
from app.services import github_service


def _new_id() -> str:
    return uuid.uuid4().hex


async def _assert_within_plan_limit(db: AsyncSession, user_id: str, plan: str) -> None:
    limit = (
        settings.PRO_PLAN_REPO_LIMIT
        if plan == "pro"
        else settings.FREE_PLAN_REPO_LIMIT
    )
    result = await db.execute(
        select(func.count())
        .select_from(Repository)
        .where(Repository.userId == user_id)
    )
    if (result.scalar_one() or 0) >= limit:
        raise PlanLimitExceededError(
            f"Your plan allows up to {limit} connected repositories"
        )


async def get_owned_repository(
    db: AsyncSession, repo_id: str, user_id: str
) -> Repository:
    """
    Fetch a repository, verifying it belongs to `user_id`.

    Returns 404 rather than 403 when the repo exists but belongs to
    someone else, so the endpoint doesn't leak which IDs are real.
    """
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()

    if repo is None:
        raise NotFoundError("Repository not found")
    if repo.userId != user_id:
        raise NotFoundError("Repository not found")

    return repo


async def list_connected(db: AsyncSession, user_id: str) -> list[Repository]:
    result = await db.execute(
        select(Repository)
        .where(Repository.userId == user_id)
        .order_by(Repository.createdAt.desc())
    )
    return list(result.scalars().all())


async def connect_repository(
    db: AsyncSession,
    user_id: str,
    plan: str,
    github_repo_id: int,
    full_name: str,
) -> tuple[Repository, Job]:
    """
    Connect a GitHub repo and queue it for ingestion.

    Steps, in order, so we fail before doing expensive work:
      1. plan limit check
      2. duplicate check
      3. verify the repo exists AND this user's token can see it
         (prevents connecting a repo you don't have access to by
         guessing its ID)
      4. size check
      5. create Repository + Job rows in one transaction
      6. enqueue the Celery ingestion task
    """
    await _assert_within_plan_limit(db, user_id, plan)

    existing = await db.execute(
        select(Repository).where(
            Repository.userId == user_id,
            Repository.githubRepoId == github_repo_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Repository is already connected")

    token = await github_service.get_user_github_token(db, user_id)
    metadata = await github_service.get_repository(token, full_name)

    # Guard against a client sending a full_name that doesn't match the ID.
    if metadata["id"] != github_repo_id:
        raise ForbiddenError("Repository identifier mismatch")

    size_mb = metadata.get("size", 0) / 1024
    if size_mb > settings.MAX_REPO_SIZE_MB:
        raise RepositoryTooLargeError(
            f"Repository is {size_mb:.0f}MB; the limit is {settings.MAX_REPO_SIZE_MB}MB"
        )

    repo = Repository(
        id=_new_id(),
        userId=user_id,
        githubRepoId=github_repo_id,
        fullName=metadata["full_name"],
        defaultBranch=metadata.get("default_branch", "main"),
        visibility="private" if metadata["private"] else "public",
        indexingStatus="pending",
    )
    job = Job(
        id=_new_id(),
        repository_id=repo.id,
        job_type="ingest",
        status="queued",
    )

    db.add(repo)
    db.add(job)
    await db.commit()
    await db.refresh(repo)
    await db.refresh(job)

    # Enqueue only after commit - otherwise the worker could start and
    # query for a row this transaction hasn't written yet.
    from app.workers.tasks.ingest import ingest_repository

    ingest_repository.delay(repository_id=repo.id, job_id=job.id)

    return repo, job


async def request_reindex(
    db: AsyncSession, repo_id: str, user_id: str
) -> Job:
    """Queue a re-ingestion, refusing if one is already in flight."""
    repo = await get_owned_repository(db, repo_id, user_id)

    if repo.indexingStatus == "processing":
        raise ConflictError("This repository is already being indexed")

    job = Job(
        id=_new_id(),
        repository_id=repo.id,
        job_type="ingest",
        status="queued",
    )
    repo.indexingStatus = "pending"
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.workers.tasks.ingest import ingest_repository

    ingest_repository.delay(repository_id=repo.id, job_id=job.id)
    return job


async def disconnect_repository(
    db: AsyncSession, repo_id: str, user_id: str
) -> None:
    """
    Remove a repository and all derived data.

    Cascades handle repo_files, code_chunks, chat_sessions and jobs.
    """
    repo = await get_owned_repository(db, repo_id, user_id)
    await db.delete(repo)
    await db.commit()


async def list_available_repositories(
    db: AsyncSession, user_id: str, page: int = 1
) -> list:
    """
    List the user's GitHub repos, flagging which are already connected
    so the UI can disable them rather than letting the user hit a 409.
    """
    token = await github_service.get_user_github_token(db, user_id)
    repos = await github_service.list_user_repositories(token, page=page)

    connected = await db.execute(
        select(Repository.githubRepoId).where(Repository.userId == user_id)
    )
    connected_ids = set(connected.scalars().all())

    for repo in repos:
        repo.already_connected = repo.github_repo_id in connected_ids

    return repos
