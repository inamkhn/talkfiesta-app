"""Accept a verified recording and credit progress in one transaction."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    ValidationAppError,
)
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.jobs.models import AiJob, OutboxEvent
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.media.models import MediaUpload
from app.modules.media.service import MediaService, utc
from app.modules.media.speaking import SpeakingMediaService
from app.modules.practice.models import PracticeSubmission, SpeakingSubmitRequest
from app.modules.speaking.schemas import SubmitSpeakingResponse


class SpeakingSubmissionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def submit(
        self, user_id: UUID, submission_id: UUID, media_id: UUID, key: str
    ) -> SubmitSpeakingResponse:
        try:
            result = await self._submit(user_id, submission_id, media_id, key)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _submit(
        self, user_id: UUID, submission_id: UUID, media_id: UUID, key: str
    ) -> SubmitSpeakingResponse:
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
            raise NotFoundError("Speaking submission not found.")
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        prior = await self.session.get(SpeakingSubmitRequest, (user_id, key_hash))
        if prior is not None and (
            prior.submission_id != submission_id or prior.media_upload_id != media_id
        ):
            raise ConflictError(
                "This key was used for a different submission or recording.",
                code="IDEMPOTENCY_CONFLICT",
            )
        if draft.status == "ACCEPTED":
            if draft.media_upload_id != media_id:
                raise ConflictError(
                    "This submission was accepted with different audio.",
                    code="IDEMPOTENCY_CONFLICT",
                )
            receipt = prior or await self.session.scalar(
                select(SpeakingSubmitRequest)
                .where(
                    SpeakingSubmitRequest.user_id == user_id,
                    SpeakingSubmitRequest.submission_id == submission_id,
                    SpeakingSubmitRequest.media_upload_id == media_id,
                )
                .limit(1)
            )
            if receipt is None:
                raise ConflictError(
                    "The saved acceptance receipt is missing.",
                    code="SPEAKING_STATE_INCONSISTENT",
                )
            result = SubmitSpeakingResponse.model_validate_json(
                json.dumps(receipt.response)
            )
            if prior is None:
                self.remember(user_id, key_hash, submission_id, media_id, result)
            return result
        if prior is not None:
            raise ConflictError(
                "The saved submission state is inconsistent.",
                code="SPEAKING_STATE_INCONSISTENT",
            )
        # Same user -> plan/progress -> content -> draft order as upload/re-record.
        draft = await SpeakingMediaService(self.session).lock_draft(
            user_id, submission_id
        )
        if draft.media_upload_id != media_id:
            raise ConflictError(
                "Submit the recording currently attached to this draft.",
                code="UPLOAD_NOT_BOUND",
            )
        upload = await self.session.scalar(
            select(MediaUpload)
            .where(
                MediaUpload.id == media_id,
                MediaUpload.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        now = datetime.now(UTC)
        if (
            upload is None
            or upload.purpose != "SPEAKING"
            or upload.status != "VERIFIED"
            or upload.verified_at is None
            or upload.content_type != "audio/webm"
            or upload.delete_after is None
            or utc(upload.delete_after) <= now
        ):
            raise ConflictError(
                "The recording must be verified and unexpired.",
                code="MEDIA_UPLOAD_NOT_VERIFIED",
            )
        if (
            upload.size_bytes is None
            or upload.size_bytes <= 0
            or upload.size_bytes != upload.expected_size_bytes
            or not upload.checksum_sha256
        ):
            raise ConflictError(
                "The verified recording metadata is incomplete.",
                code="MEDIA_UPLOAD_NOT_VERIFIED",
            )
        if upload.size_bytes > settings.speaking_audio_max_bytes:
            raise PayloadTooLargeError(
                "The recording exceeds the Speaking upload limit.",
                code="AUDIO_TOO_LARGE",
            )
        duration = upload.duration_seconds
        if (
            duration is None
            or not duration.is_finite()
            or not settings.speaking_audio_min_duration_seconds
            <= duration
            <= settings.speaking_audio_max_duration_seconds
        ):
            raise ValidationAppError(
                "The recording duration is outside the Speaking limits.",
                code="RECORDING_DURATION_OUT_OF_RANGE",
            )
        reused = await self.session.scalar(
            select(PracticeSubmission.id)
            .where(
                PracticeSubmission.media_upload_id == media_id,
                PracticeSubmission.status == "ACCEPTED",
                PracticeSubmission.id != submission_id,
            )
            .limit(1)
        )
        if reused is not None:
            raise ConflictError(
                "This recording has already been accepted.", code="IDEMPOTENCY_CONFLICT"
            )
        progress = await self.session.get(ModuleProgress, draft.module_progress_id)
        plan = await self.session.get(LearningPlan, progress.learning_plan_id)
        item = await self.session.get(ContentItem, draft.content_item_id)
        # Refuse corrupt progress rather than marking day 21 complete with gaps.
        credited_days = set(
            await self.session.scalars(
                select(ContentItem.day)
                .join(
                    ActivityCompletion,
                    ActivityCompletion.content_item_id == ContentItem.id,
                )
                .where(
                    ActivityCompletion.user_id == user_id,
                    ActivityCompletion.module_progress_id == progress.id,
                    ContentItem.release_key == progress.content_release,
                    ContentItem.module == "SPEAKING",
                    ContentItem.kind == "SPEAKING_LESSON",
                    ContentItem.slot == "CORE",
                    ContentItem.cycle == plan.cycle,
                    ContentItem.cefr_level == progress.cefr_level,
                    ContentItem.goal_variant == progress.goal_variant,
                    ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
                )
            )
        )
        day = progress.current_day
        if credited_days != set(range(1, day)):
            raise ConflictError(
                "Speaking progress and completion credits disagree.",
                code="SPEAKING_STATE_INCONSISTENT",
            )
        user = await self.session.get(User, user_id)
        draft.status = "ACCEPTED"
        draft.evaluation_status = "PENDING"
        draft.submitted_at = now
        draft.input = {
            "media_upload_id": str(media_id),
            "content_item_id": str(item.id),
            "content_version": item.content_version,
            "content_release": progress.content_release,
            "day": day,
            "target_cefr": progress.cefr_level,
            "content_type": upload.content_type,
            "size_bytes": upload.size_bytes,
            "duration_seconds": str(duration),
            "checksum_sha256": upload.checksum_sha256,
        }
        self.session.add(
            ActivityCompletion(
                user_id=user_id,
                module_progress_id=progress.id,
                content_item_id=item.id,
                source_submission_id=draft.id,
                local_practice_date=now.astimezone(ZoneInfo(user.timezone)).date(),
                duration_seconds=int(duration),
                completed_at=now,
            )
        )
        if day == 21:
            progress.status = "COMPLETED"
            progress.completed_at = now
        else:
            progress.current_day = day + 1
        progress.updated_at = now
        job = AiJob(
            id=uuid4(),
            user_id=user_id,
            job_type="SPEAKING_FEEDBACK",
            practice_submission_id=draft.id,
            status="PENDING",
            idempotency_key=f"speaking:{draft.id}:feedback:v1",
        )
        self.session.add(job)
        await self.session.flush()
        self.session.add(
            OutboxEvent(
                ai_job_id=job.id,
                event_type="SPEAKING_FEEDBACK_REQUESTED",
                payload={
                    "job_id": str(job.id),
                    "practice_submission_id": str(draft.id),
                },
            )
        )
        result = SubmitSpeakingResponse(
            submission_id=draft.id,
            job_id=job.id,
            credited_day=day,
            next_speaking_day=day + 1 if day < 21 else None,
            submission_url=f"/api/v1/speaking/submissions/{draft.id}",
        )
        self.remember(user_id, key_hash, submission_id, media_id, result)
        return result

    def remember(self, user_id, key_hash, submission_id, media_id, result):
        self.session.add(
            SpeakingSubmitRequest(
                user_id=user_id,
                key_hash=key_hash,
                submission_id=submission_id,
                media_upload_id=media_id,
                response=result.model_dump(mode="json"),
            )
        )
