"""Private assessment and Speaking audio upload allocation and confirmation."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import Field

from app.api.deps import CurrentUser, DbSession
from app.infrastructure.cache.redis import enforce_rate_limit
from app.modules.media.schemas import (
    AudioUploadConfirmed,
    AudioUploadCreated,
    CreateAudioUpload,
    CreateSpeakingAudioUpload,
    SpeakingAudioUploadConfirmed,
    SpeakingAudioUploadCreated,
)
from app.modules.media.service import MediaService

router = APIRouter(prefix="/media/audio-uploads", tags=["Media"])


@router.post(
    "", status_code=201, response_model=AudioUploadCreated | SpeakingAudioUploadCreated
)
async def create_upload(
    payload: Annotated[
        CreateAudioUpload | CreateSpeakingAudioUpload, Field(discriminator="purpose")
    ],
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> AudioUploadCreated | SpeakingAudioUploadCreated:
    await enforce_rate_limit(
        f"ratelimit:audio-create:{user.id}", limit=20, window_seconds=3600
    )
    response.headers["Cache-Control"] = "no-store"
    if isinstance(payload, CreateSpeakingAudioUpload):
        from app.modules.media.speaking import SpeakingMediaService

        return await SpeakingMediaService(db).create(user.id, payload)
    return await MediaService(db).create(user.id, payload)


@router.post(
    "/{upload_id}/confirm",
    response_model=AudioUploadConfirmed | SpeakingAudioUploadConfirmed,
)
async def confirm_upload(
    upload_id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> AudioUploadConfirmed | SpeakingAudioUploadConfirmed:
    await enforce_rate_limit(
        f"ratelimit:audio-confirm:{user.id}", limit=40, window_seconds=3600
    )
    response.headers["Cache-Control"] = "no-store"
    return await MediaService(db).confirm(user.id, upload_id)
