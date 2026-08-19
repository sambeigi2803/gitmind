# app/api/v1/routes/jobs.py
"""Job status endpoints - used by the UI to poll ingestion progress."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.models.repository import Job
from app.schemas.repository import JobResponse
from app.services import repository_service

router = APIRouter(tags=["jobs"])


@router.get("/repos/{repo_id}/jobs", response_model=list[JobResponse])
async def list_repository_jobs(
    repo_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Ownership check happens here before any job data is read.
    await repository_service.get_owned_repository(db, repo_id, user.id)

    result = await db.execute(
        select(Job).where(Job.repository_id == repo_id).order_by(Job.created_at.desc())
    )
    return [JobResponse.model_validate(j) for j in result.scalars().all()]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise NotFoundError("Job not found")

    # Verify the caller owns the repository this job belongs to.
    await repository_service.get_owned_repository(db, job.repository_id, user.id)
    return JobResponse.model_validate(job)
