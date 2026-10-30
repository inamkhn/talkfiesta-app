"""Composition root for ``/api/v1``: mount one router per feature."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.account_router import router as account_router
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(account_router)
api_router.include_router(users_router)
