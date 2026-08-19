# app/services/github_service.py
"""
Thin async client for the GitHub REST API.

Responsibilities:
  - fetch the caller's decrypted token from the `accounts` table
  - list repositories with pagination
  - fetch repo metadata

Deliberately does NOT know about HTTP status codes or FastAPI - it
raises domain exceptions so the same code works inside Celery workers.
"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import GithubAPIError, GithubReauthRequiredError
from app.core.security import decrypt_token
from app.models.repository import Account
from app.schemas.repository import GithubRepoSummary

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def get_user_github_token(db: AsyncSession, user_id: str) -> str:
    """
    Return the decrypted GitHub token for a user.

    Raises GithubReauthRequiredError if no account is linked or the
    stored ciphertext can't be decrypted (e.g. ENCRYPTION_KEY rotated).
    """
    result = await db.execute(
        select(Account.access_token).where(
            Account.userId == user_id, Account.provider == "github"
        )
    )
    encrypted = result.scalar_one_or_none()

    if not encrypted:
        raise GithubReauthRequiredError("No GitHub account linked")

    try:
        return decrypt_token(encrypted)
    except Exception as exc:
        raise GithubReauthRequiredError(
            "Stored GitHub token could not be decrypted"
        ) from exc


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def list_user_repositories(
    token: str, page: int = 1, per_page: int = 30
) -> list[GithubRepoSummary]:
    """List repos the token's owner can access, most recently pushed first."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{settings.GITHUB_API_URL}/user/repos",
            headers=_headers(token),
            params={
                "per_page": min(per_page, 100),
                "page": page,
                "sort": "pushed",
                "affiliation": "owner,collaborator,organization_member",
            },
        )

    if response.status_code == 401:
        raise GithubReauthRequiredError("GitHub rejected the stored token")
    if response.status_code != 200:
        raise GithubAPIError(f"GitHub returned {response.status_code}")

    return [
        GithubRepoSummary(
            github_repo_id=item["id"],
            full_name=item["full_name"],
            description=item.get("description"),
            private=item["private"],
            default_branch=item.get("default_branch", "main"),
            language=item.get("language"),
            stargazers_count=item.get("stargazers_count", 0),
            size_kb=item.get("size", 0),
            updated_at=item.get("pushed_at"),
        )
        for item in response.json()
    ]


async def get_repository(token: str, full_name: str) -> dict:
    """Fetch metadata for a single repo, used to validate a connect request."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{full_name}",
            headers=_headers(token),
        )

    if response.status_code == 401:
        raise GithubReauthRequiredError("GitHub rejected the stored token")
    if response.status_code == 404:
        # 404 also covers "exists but this token can't see it" - GitHub
        # deliberately doesn't distinguish, and neither should we.
        raise GithubAPIError("Repository not found or not accessible")
    if response.status_code != 200:
        raise GithubAPIError(f"GitHub returned {response.status_code}")

    return response.json()
