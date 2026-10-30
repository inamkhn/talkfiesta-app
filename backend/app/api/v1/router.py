"""Composition root for ``/api/v1``: mount one router per feature."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
