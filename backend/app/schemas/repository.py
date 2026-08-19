# app/schemas/repository.py
"""
Pydantic schemas: the API contract.

Kept separate from ORM models so internal columns (encrypted tokens,
user IDs) can never leak into a response by accident.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

IndexingStatus = Literal["pending", "processing", "done", "failed"]


class GithubRepoSummary(BaseModel):
    """A repo as returned live from the GitHub API (not yet connected)."""

    github_repo_id: int
    full_name: str
    description: str | None = None
    private: bool
    default_branch: str
    language: str | None = None
    stargazers_count: int = 0
    size_kb: int = Field(0, description="Repo size reported by GitHub, in KB")
    updated_at: datetime | None = None
    already_connected: bool = False

    # GitHub IDs exceed 32-bit; serialize as string so JS clients don't
    # silently lose precision past Number.MAX_SAFE_INTEGER.
    @field_serializer("github_repo_id")
    def _serialize_id(self, value: int) -> str:
        return str(value)


class ConnectRepositoryRequest(BaseModel):
    github_repo_id: int
    full_name: str = Field(pattern=r"^[\w.-]+/[\w.-]+$")


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    default_branch: str | None
    visibility: str | None
    indexing_status: IndexingStatus
    last_indexed_at: datetime | None
    created_at: datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    status: str
    progress: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ConnectRepositoryResponse(BaseModel):
    repository: RepositoryResponse
    job: JobResponse
