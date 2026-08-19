# app/api/v1/routes/repositories.py
"""
Repository endpoints.

Routes stay thin: parse input, call a service, return a schema. All
authorization lives in the service layer.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.repository import (
    ConnectRepositoryRequest,
    ConnectRepositoryResponse,
    GithubRepoSummary,
    JobResponse,
    RepositoryResponse,
)
from app.services import repository_service

router = APIRouter(prefix="/repos", tags=["repositories"])


def _to_response(repo) -> RepositoryResponse:
    """Map ORM camelCase columns to the snake_case API contract."""
    return RepositoryResponse(
        id=repo.id,
        full_name=repo.fullName,
        default_branch=repo.defaultBranch,
        visibility=repo.visibility,
        indexing_status=repo.indexingStatus,
        last_indexed_at=repo.lastIndexedAt,
        created_at=repo.createdAt,
    )


@router.get("/available", response_model=list[GithubRepoSummary])
async def list_available_repositories(
    page: int = Query(1, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Live list of the user's GitHub repos, with connection status."""
    return await repository_service.list_available_repositories(db, user.id, page)


@router.get("", response_model=list[RepositoryResponse])
async def list_connected_repositories(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repos = await repository_service.list_connected(db, user.id)
    return [_to_response(r) for r in repos]


@router.post(
    "/connect",
    response_model=ConnectRepositoryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def connect_repository(
    payload: ConnectRepositoryRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect a repo and queue ingestion.

    Returns 202 - ingestion runs in the background; poll the returned
    job or GET the repository for status.
    """
    repo, job = await repository_service.connect_repository(
        db,
        user_id=user.id,
        plan=user.plan,
        github_repo_id=payload.github_repo_id,
        full_name=payload.full_name,
    )
    return ConnectRepositoryResponse(
        repository=_to_response(repo),
        job=JobResponse.model_validate(job),
    )


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = await repository_service.get_owned_repository(db, repo_id, user.id)
    return _to_response(repo)


@router.post(
    "/{repo_id}/reindex",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reindex_repository(
    repo_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await repository_service.request_reindex(db, repo_id, user.id)
    return JobResponse.model_validate(job)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_repository(
    repo_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await repository_service.disconnect_repository(db, repo_id, user.id)
