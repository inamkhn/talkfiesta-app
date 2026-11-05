"""Assessment-bound upload lifecycle using the shared assessment lock order."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from app.infrastructure.storage.audio import inspect_audio, require_decoder
from app.infrastructure.storage.s3 import presign, read_audio, require_storage
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.assessment.repository import AssessmentRepository
from app.modules.content.models import ContentItem
from app.modules.media.models import MediaUpload
from app.modules.media.schemas import (
    AudioUploadConfirmed,
    AudioUploadCreated,
    CreateAudioUpload,
    SpeakingAudioUploadConfirmed,
)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class MediaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_user(self, user_id: UUID) -> None:
        user = await AssessmentRepository(self.session).lock_user(user_id)
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

    async def lock_response(self, user_id: UUID, response_id: UUID):
        # Locate through ownership before acquiring attempt -> response locks.
        attempt_id = await self.session.scalar(
            select(AssessmentResponse.assessment_attempt_id)
            .join(
                AssessmentAttempt,
                AssessmentAttempt.id == AssessmentResponse.assessment_attempt_id,
            )
            .where(
                AssessmentResponse.id == response_id,
                AssessmentAttempt.user_id == user_id,
            )
        )
        if attempt_id is None:
            raise NotFoundError("Assigned assessment response not found.")
        attempt = await self.session.scalar(
            select(AssessmentAttempt)
            .where(AssessmentAttempt.id == attempt_id)
            .with_for_update()
        )
        response = await self.session.scalar(
            select(AssessmentResponse)
            .where(AssessmentResponse.id == response_id)
            .with_for_update()
        )
        return attempt, response

    async def require_editable(
        self, attempt: AssessmentAttempt, response: AssessmentResponse
    ) -> None:
        if attempt.status != "IN_PROGRESS" or response.status != "ASSIGNED":
            raise ConflictError(
                "Audio can only be uploaded for an unanswered, editable assessment response.",
                code="ASSESSMENT_NOT_EDITABLE",
            )
        item = await self.session.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == response.question_content_id,
                ContentItem.kind == "ASSESSMENT_QUESTION",
                ContentItem.release_key == attempt.content_release,
                ContentItem.status == "PUBLISHED",
            )
            .with_for_update(read=True)
        )
        if (
            item is None
            or not isinstance(item.body, dict)
            or item.body.get("kind") != "RECORDED_SPEAKING"
            or item.body.get("skill") != "SPEAKING"
        ):
            raise ValidationAppError(
                "The assigned question does not accept speaking audio."
            )

    async def create(
        self, user_id: UUID, payload: CreateAudioUpload
    ) -> AudioUploadCreated:
        require_storage()
        require_decoder()
        if payload.size_bytes > settings.audio_max_bytes:
            raise ValidationAppError(
                f"Audio must not exceed {settings.audio_max_bytes} bytes."
            )
        await self.lock_user(user_id)
        attempt, response = await self.lock_response(
            user_id, payload.assessment_response_id
        )
        await self.require_editable(attempt, response)
        now = datetime.now(UTC)
        upload = MediaUpload(
            id=uuid4(),
            user_id=user_id,
            purpose="ASSESSMENT",
            assessment_response_id=response.id,
            object_key=f"assessment-audio/{uuid4().hex}",
            content_type=payload.content_type,
            expected_size_bytes=payload.size_bytes,
            checksum_sha256=payload.checksum_sha256,
            status="INITIATED",
            upload_expires_at=now
            + timedelta(seconds=settings.audio_upload_url_seconds),
            delete_after=now + timedelta(days=settings.audio_retention_days),
        )
        url = await asyncio.to_thread(
            presign,
            upload.object_key,
            upload.content_type,
            payload.size_bytes,
            payload.checksum_sha256,
        )
        self.session.add(upload)
        await self.session.flush()
        response.media_upload_id = upload.id
        await self.session.commit()
        return AudioUploadCreated(
            upload_id=upload.id,
            upload_url=url,
            expires_at=upload.upload_expires_at,
            headers={
                "Content-Type": upload.content_type,
                "x-amz-checksum-sha256": payload.checksum_sha256,
                "If-None-Match": "*",
            },
        )

    async def confirm(
        self, user_id: UUID, upload_id: UUID
    ) -> AudioUploadConfirmed | SpeakingAudioUploadConfirmed:
        await self.lock_user(user_id)
        upload = await self.session.scalar(
            select(MediaUpload).where(
                MediaUpload.id == upload_id, MediaUpload.user_id == user_id
            )
        )
        if upload is not None and upload.purpose == "SPEAKING":
            from app.modules.media.speaking import SpeakingMediaService

            return await SpeakingMediaService(self.session).confirm(user_id, upload_id)
        if (
            upload is None
            or upload.purpose != "ASSESSMENT"
            or upload.assessment_response_id is None
        ):
            raise NotFoundError("Assessment audio upload not found.")
        attempt, response = await self.lock_response(
            user_id, upload.assessment_response_id
        )
        upload = await self.session.scalar(
            select(MediaUpload)
            .where(MediaUpload.id == upload_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if response.media_upload_id != upload.id:
            raise ConflictError(
                "This upload has been replaced or detached.", code="UPLOAD_NOT_BOUND"
            )
        now = datetime.now(UTC)
        if upload.delete_after is None or utc(upload.delete_after) <= now:
            raise ConflictError("This upload has expired.", code="UPLOAD_EXPIRED")
        if upload.status == "VERIFIED":
            return self.result(upload)
        if upload.status != "INITIATED":
            raise ConflictError(
                "Create a new upload for this recording.", code="UPLOAD_NOT_CONFIRMABLE"
            )
        await self.require_editable(attempt, response)
        if upload.upload_expires_at is None or now > utc(
            upload.upload_expires_at
        ) + timedelta(minutes=15):
            raise ConflictError(
                "The upload confirmation window has expired.", code="UPLOAD_EXPIRED"
            )
        if upload.expected_size_bytes is None or upload.checksum_sha256 is None:
            raise ConflictError(
                "Create a new upload with size and checksum.",
                code="UPLOAD_NOT_CONFIRMABLE",
            )
        require_decoder()
        try:
            data = await asyncio.to_thread(
                read_audio,
                upload.object_key,
                upload.content_type,
                upload.expected_size_bytes,
                upload.checksum_sha256,
            )
            duration = await asyncio.to_thread(inspect_audio, data, upload.content_type)
        except ValidationAppError:
            upload.status = "REJECTED"
            await self.session.commit()
            raise
        upload.status = "VERIFIED"
        upload.size_bytes = len(data)
        upload.duration_seconds = duration
        upload.verified_at = datetime.now(UTC)
        await self.session.commit()
        return self.result(upload)

    @staticmethod
    def result(upload: MediaUpload) -> AudioUploadConfirmed:
        return AudioUploadConfirmed(
            upload_id=upload.id,
            assessment_response_id=upload.assessment_response_id,
            size_bytes=upload.size_bytes,
            duration_seconds=upload.duration_seconds,
        )
