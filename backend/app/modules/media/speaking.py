"""Private audio allocation and verification for the currently assigned draft."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    ValidationAppError,
)
from app.infrastructure.storage.audio import inspect_audio, require_decoder
from app.infrastructure.storage.s3 import presign, read_audio, require_storage
from app.modules.content.models import ContentItem
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.media.models import MediaUpload
from app.modules.media.schemas import (
    CreateSpeakingAudioUpload,
    SpeakingAudioUploadConfirmed,
    SpeakingAudioUploadCreated,
)
from app.modules.media.service import MediaService, utc
from app.modules.practice.models import PracticeSubmission
from app.modules.speaking.service import SpeakingQueryService


class SpeakingMediaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_draft(self, user_id: UUID, submission_id: UUID):
        await MediaService(self.session).lock_user(user_id)
        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.id == submission_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "RECORDED_SPEAKING",
            )
            .execution_options(populate_existing=True)
        )
        if draft is None:
            raise NotFoundError("Speaking draft not found.")
        await self.session.execute(
            select(LearningPlan, ModuleProgress)
            .join(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
            .where(
                LearningPlan.user_id == user_id,
                ModuleProgress.id == draft.module_progress_id,
            )
            .with_for_update(of=(LearningPlan, ModuleProgress))
        )
        await self.session.execute(
            select(ContentItem.id)
            .where(ContentItem.id == draft.content_item_id)
            .with_for_update(read=True, of=ContentItem)
        )
        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.id == submission_id,
                PracticeSubmission.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if draft is None:
            raise NotFoundError("Speaking draft not found.")
        if draft.status != "DRAFT":
            raise ConflictError(
                "Audio can only be attached to an active draft.",
                code="DRAFT_NOT_EDITABLE",
            )
        today = await SpeakingQueryService(self.session).get_today(user_id)
        if (
            today.activity is None
            or today.module_progress_id != draft.module_progress_id
            or today.activity.id != draft.content_item_id
        ):
            raise ConflictError(
                "This draft is no longer the current activity.",
                code="ACTIVITY_NOT_CURRENT",
            )
        credit = await self.session.scalar(
            select(ActivityCompletion.id).where(
                ActivityCompletion.user_id == user_id,
                ActivityCompletion.module_progress_id == draft.module_progress_id,
                ActivityCompletion.content_item_id == draft.content_item_id,
            )
        )
        if credit is not None:
            raise ConflictError(
                "This activity is already completed.", code="ACTIVITY_ALREADY_COMPLETED"
            )
        return draft

    @staticmethod
    def require_policy():
        require_storage()
        require_decoder()
        if (
            settings.speaking_audio_min_duration_seconds
            > settings.speaking_audio_max_duration_seconds
        ):
            raise ServiceUnavailableError(
                "Speaking audio duration settings are invalid."
            )

    async def create(
        self, user_id: UUID, payload: CreateSpeakingAudioUpload
    ) -> SpeakingAudioUploadCreated:
        self.require_policy()
        if payload.size_bytes > settings.speaking_audio_max_bytes:
            raise PayloadTooLargeError(
                f"Speaking audio must not exceed {settings.speaking_audio_max_bytes} bytes."
            )
        draft = await self.lock_draft(user_id, payload.submission_id)
        now = datetime.now(UTC)
        upload = MediaUpload(
            id=uuid4(),
            user_id=user_id,
            purpose="SPEAKING",
            object_key=f"speaking-audio/{uuid4().hex}",
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
        draft.media_upload_id = upload.id
        await self.session.commit()
        return SpeakingAudioUploadCreated(
            upload_id=upload.id,
            upload_url=url,
            expires_at=upload.upload_expires_at,
            required_headers={
                "Content-Type": upload.content_type,
                "x-amz-checksum-sha256": payload.checksum_sha256,
                "If-None-Match": "*",
            },
        )

    async def confirm(
        self, user_id: UUID, upload_id: UUID
    ) -> SpeakingAudioUploadConfirmed:
        await MediaService(self.session).lock_user(user_id)
        submission_id = await self.session.scalar(
            select(PracticeSubmission.id).where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.media_upload_id == upload_id,
                PracticeSubmission.mode == "RECORDED_SPEAKING",
            )
        )
        if submission_id is None:
            raise ConflictError(
                "This upload has been replaced or detached.", code="UPLOAD_NOT_BOUND"
            )
        draft = await self.lock_draft(user_id, submission_id)
        upload = await self.session.scalar(
            select(MediaUpload)
            .where(
                MediaUpload.id == upload_id,
                MediaUpload.user_id == user_id,
                MediaUpload.purpose == "SPEAKING",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if upload is None:
            raise NotFoundError("Speaking audio upload not found.")
        if draft.media_upload_id != upload.id:
            raise ConflictError(
                "This upload has been replaced or detached.", code="UPLOAD_NOT_BOUND"
            )
        now = datetime.now(UTC)
        if upload.delete_after is None or utc(upload.delete_after) <= now:
            raise ConflictError("This upload has expired.", code="UPLOAD_EXPIRED")
        if upload.status == "VERIFIED":
            return self.result(upload, draft.id)
        if upload.status != "INITIATED":
            raise ConflictError(
                "Create a new upload for this recording.", code="UPLOAD_NOT_CONFIRMABLE"
            )
        if upload.upload_expires_at is None or now > utc(
            upload.upload_expires_at
        ) + timedelta(minutes=15):
            raise ConflictError(
                "The upload confirmation window has expired.", code="UPLOAD_EXPIRED"
            )
        if (
            upload.expected_size_bytes is None
            or upload.checksum_sha256 is None
            or upload.content_type != "audio/webm"
        ):
            raise ConflictError(
                "Create a new WebM upload with size and checksum.",
                code="UPLOAD_NOT_CONFIRMABLE",
            )
        self.require_policy()
        try:
            data = await asyncio.to_thread(
                read_audio,
                upload.object_key,
                upload.content_type,
                upload.expected_size_bytes,
                upload.checksum_sha256,
                max_bytes=settings.speaking_audio_max_bytes,
            )
            duration = await asyncio.to_thread(
                inspect_audio,
                data,
                upload.content_type,
                min_seconds=Decimal(settings.speaking_audio_min_duration_seconds),
                max_seconds=settings.speaking_audio_max_duration_seconds,
                required_codec="opus",
            )
        except ValidationAppError:
            upload.status = "REJECTED"
            await self.session.commit()
            raise
        upload.status = "VERIFIED"
        upload.size_bytes = len(data)
        upload.duration_seconds = duration
        upload.verified_at = datetime.now(UTC)
        await self.session.commit()
        return self.result(upload, draft.id)

    @staticmethod
    def result(
        upload: MediaUpload, submission_id: UUID
    ) -> SpeakingAudioUploadConfirmed:
        return SpeakingAudioUploadConfirmed(
            upload_id=upload.id,
            submission_id=submission_id,
            content_type=upload.content_type,
            size_bytes=upload.size_bytes,
            duration_seconds=upload.duration_seconds,
            verified_at=upload.verified_at,
        )
