# app/models/repository.py
"""
SQLAlchemy models for the tables owned by the ingestion/chat pipeline.

IMPORTANT: Prisma (frontend) owns the migrations for `users`, `accounts`,
`sessions`. These models mirror the columns the backend needs to READ -
the backend never migrates those tables. Tables the backend does own
(repo_files, code_chunks, jobs) are migrated here via Alembic.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    """Read-only mirror of the Prisma-owned `users` table."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    plan: Mapped[str] = mapped_column(String, default="free")

    repositories: Mapped[list["Repository"]] = relationship(back_populates="user")


class Account(Base):
    """Read-only mirror of Prisma-owned `accounts`. Holds encrypted tokens."""

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    userId: Mapped[str] = mapped_column("userId", String, ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String)
    providerAccountId: Mapped[str] = mapped_column("providerAccountId", String)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    userId: Mapped[str] = mapped_column(
        "userId", String, ForeignKey("users.id", ondelete="CASCADE")
    )
    githubRepoId: Mapped[int] = mapped_column("githubRepoId", BigInteger)
    fullName: Mapped[str] = mapped_column("fullName", String)
    defaultBranch: Mapped[str | None] = mapped_column("defaultBranch", String)
    visibility: Mapped[str | None] = mapped_column(String)
    indexingStatus: Mapped[str] = mapped_column("indexingStatus", String, default="pending")
    lastIndexedAt: Mapped[datetime | None] = mapped_column(
        "lastIndexedAt", DateTime(timezone=True)
    )
    createdAt: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="repositories")
    files: Mapped[list["RepoFile"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("userId", "githubRepoId", name="uq_repo_user_github"),
        Index("ix_repositories_user_id", "userId"),
    )


class RepoFile(Base):
    """One row per indexed source file."""

    __tablename__ = "repo_files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repository_id: Mapped[str] = mapped_column(
        String, ForeignKey("repositories.id", ondelete="CASCADE")
    )
    file_path: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(50))
    # Git blob SHA - lets re-indexing skip unchanged files entirely,
    # which is the single biggest cost saving on re-ingestion.
    sha: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    repository: Mapped[Repository] = relationship(back_populates="files")

    __table_args__ = (
        Index("ix_repo_files_repository_id", "repository_id"),
        UniqueConstraint("repository_id", "file_path", name="uq_repo_file_path"),
    )


class Job(Base):
    """Tracks long-running background work so the UI can poll status."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repository_id: Mapped[str] = mapped_column(
        String, ForeignKey("repositories.id", ondelete="CASCADE")
    )
    job_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_jobs_repository_id", "repository_id"),)
