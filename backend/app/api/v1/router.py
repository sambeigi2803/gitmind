# app/api/v1/router.py
"""Aggregates all v1 routers under a single prefix."""

from fastapi import APIRouter

from app.api.v1.routes import jobs, repositories

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(repositories.router)
api_router.include_router(jobs.router)
