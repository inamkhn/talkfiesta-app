from fastapi import APIRouter

from app.api.v1 import (
    auth,
    speaking,
    writing,
    vocabulary,
    live,
    progress,
    interview
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(speaking.router, prefix="/speaking", tags=["Speaking"])
api_router.include_router(writing.router, prefix="/writing", tags=["Writing"])
api_router.include_router(vocabulary.router, prefix="/vocabulary", tags=["Vocabulary"])
api_router.include_router(live.router, prefix="/speaking/live", tags=["Speaking - Live"])
api_router.include_router(progress.router, prefix="/progress", tags=["Progress"])
api_router.include_router(interview.router, prefix="/interview", tags=["Interview"])
