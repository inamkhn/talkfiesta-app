"""Private assessment audio upload allocation and confirmation."""

from uuid import UUID

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.infrastructure.cache.redis import enforce_rate_limit
from app.modules.media.schemas import (
    AudioUploadConfirmed,
    AudioUploadCreated,
    CreateAudioUpload,
)
from app.modules.media.service import MediaService

router = APIRouter(prefix="/media/audio-uploads", tags=["Media"])


@router.post("", status_code=201, response_model=AudioUploadCreated)
async def create_upload(
    payload: CreateAudioUpload, user: CurrentUser, db: DbSession, response: Response
) -> AudioUploadCreated:
    await enforce_rate_limit(
        f"ratelimit:audio-create:{user.id}", limit=20, window_seconds=3600
    )
    response.headers["Cache-Control"] = "no-store"
    return await MediaService(db).create(user.id, payload)


@router.post("/{upload_id}/confirm", response_model=AudioUploadConfirmed)
async def confirm_upload(
    upload_id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> AudioUploadConfirmed:
    await enforce_rate_limit(
        f"ratelimit:audio-confirm:{user.id}", limit=40, window_seconds=3600
    )
    response.headers["Cache-Control"] = "no-store"
    return await MediaService(db).confirm(user.id, upload_id)
