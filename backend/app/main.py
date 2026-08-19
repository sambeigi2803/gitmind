# app/main.py
"""
FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import GitMindError
from app.db.session import engine

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GitMind API (%s)", settings.ENVIRONMENT)
    yield
    # Close pooled connections cleanly so Postgres doesn't hold
    # half-open sockets after a rolling deploy.
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="GitMind API",
    version="1.0.0",
    description="AI-powered codebase explorer",
    # Hide interactive docs in production.
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(GitMindError)
async def gitmind_error_handler(request: Request, exc: GitMindError) -> JSONResponse:
    """
    Single place mapping domain exceptions to HTTP responses, so services
    never import FastAPI and every error shares one response shape.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the detail server-side; return an opaque message to the client
    # so internal structure isn't leaked.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred"}},
    )


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe for the deployment platform."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


app.include_router(api_router)
