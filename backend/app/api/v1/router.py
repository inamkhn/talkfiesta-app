"""Composition root for ``/api/v1``: mount one router per feature."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.assessment.router import router as assessment_router
from app.modules.auth.account_router import router as account_router
from app.modules.auth.router import router as auth_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.learning.router import router as learning_router
from app.modules.media.router import router as media_router
from app.modules.onboarding.router import router as onboarding_router
from app.modules.speaking.router import router as speaking_router
from app.modules.users.router import router as users_router
from app.modules.vocabulary.router import router as vocabulary_router
from app.modules.writing.router import router as writing_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(account_router)
api_router.include_router(users_router)
api_router.include_router(onboarding_router)
api_router.include_router(assessment_router)
api_router.include_router(media_router)
api_router.include_router(learning_router)
api_router.include_router(dashboard_router)
api_router.include_router(speaking_router)
api_router.include_router(vocabulary_router)
api_router.include_router(writing_router)
