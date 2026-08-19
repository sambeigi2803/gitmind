# app/core/config.py
"""
Application configuration.

All settings are loaded from environment variables and validated at
import time by pydantic-settings, so a misconfigured deployment fails
fast at startup rather than mid-request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Environment ---
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: PostgresDsn
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- Redis / Celery ---
    REDIS_URL: RedisDsn
    CELERY_BROKER_URL: RedisDsn
    CELERY_RESULT_BACKEND: RedisDsn

    # --- Auth ---
    # Must match AUTH_SECRET used by the Next.js frontend: the backend
    # verifies the same JWT the frontend issues.
    AUTH_SECRET: str = Field(min_length=32)
    # 64 hex chars / 32 bytes. Must match the frontend's ENCRYPTION_KEY
    # so the backend can decrypt stored GitHub tokens.
    ENCRYPTION_KEY: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    # --- External APIs ---
    GITHUB_API_URL: str = "https://api.github.com"
    ANTHROPIC_API_KEY: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # --- Limits ---
    MAX_REPO_SIZE_MB: int = 200
    MAX_FILE_SIZE_KB: int = 1024
    FREE_PLAN_REPO_LIMIT: int = 3
    PRO_PLAN_REPO_LIMIT: int = 50

    # --- CORS ---
    FRONTEND_ORIGIN: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """Cached so settings are parsed exactly once per process."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
