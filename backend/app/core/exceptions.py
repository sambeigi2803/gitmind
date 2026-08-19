# app/core/exceptions.py
"""
Domain exceptions.

Services raise these; a single handler in main.py maps them to HTTP
responses. This keeps service code free of HTTP concerns and makes the
same services reusable from Celery workers, where HTTPException would
be meaningless.
"""


class GitMindError(Exception):
    """Base class for all application errors."""

    status_code = 500
    code = "internal_error"
    message = "An unexpected error occurred"

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class NotFoundError(GitMindError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ForbiddenError(GitMindError):
    status_code = 403
    code = "forbidden"
    message = "You do not have access to this resource"


class ConflictError(GitMindError):
    status_code = 409
    code = "conflict"
    message = "Resource already exists"


class PlanLimitExceededError(GitMindError):
    status_code = 402
    code = "plan_limit_exceeded"
    message = "You have reached your plan's repository limit"


class GithubReauthRequiredError(GitMindError):
    """Token is missing or undecryptable - the user must reconnect GitHub."""

    status_code = 401
    code = "github_reauth_required"
    message = "GitHub re-authentication required"


class GithubAPIError(GitMindError):
    status_code = 502
    code = "github_api_error"
    message = "GitHub API request failed"


class RepositoryTooLargeError(GitMindError):
    status_code = 413
    code = "repository_too_large"
    message = "Repository exceeds the maximum supported size"
