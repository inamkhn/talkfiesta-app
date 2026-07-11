from fastapi import APIRouter

from app.api.v1 import auth, vocabulary, writing, speaking, live

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(vocabulary.router, prefix="/vocabulary", tags=["Vocabulary"])
api_router.include_router(writing.router, prefix="/writing", tags=["Writing"])
api_router.include_router(speaking.router, prefix="/speaking", tags=["Speaking"])
api_router.include_router(live.router, prefix="/speaking/live", tags=["Speaking - Live"])

