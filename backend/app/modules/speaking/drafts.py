"""Serialized, durable creation of drafts for the current speaking assignment."""

import hashlib
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.practice.models import PracticeSubmission, SpeakingDraftRequest
from app.modules.speaking.schemas import SpeakingDraftResponse
from app.modules.speaking.service import SpeakingQueryService


class SpeakingDraftService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: UUID, content_id: UUID, key: str
    ) -> tuple[SpeakingDraftResponse, bool]:
        try:
            result = await self._create(user_id, content_id, key)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _create(
        self, user_id: UUID, content_id: UUID, key: str
    ) -> tuple[SpeakingDraftResponse, bool]:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        prior = await self.session.get(SpeakingDraftRequest, (user_id, key_hash))
        if prior is not None and prior.content_item_id != content_id:
            raise ConflictError(
                "This key was used with a different request.",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        # All speaking writers must use user -> plan/progress -> content -> draft
        # lock order, including future acceptance/progress advancement.
        await self.session.execute(
            select(LearningPlan, ModuleProgress)
            .join(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "SPEAKING",
            )
            .with_for_update(of=(LearningPlan, ModuleProgress))
            .execution_options(populate_existing=True)
        )
        # Keep the selected content's published status stable until commit.
        await self.session.execute(
            select(ContentItem.id)
            .join(
                ModuleProgress,
                ModuleProgress.content_release == ContentItem.release_key,
            )
            .join(LearningPlan, LearningPlan.id == ModuleProgress.learning_plan_id)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "SPEAKING",
                ModuleProgress.status == "ACTIVE",
                ContentItem.id == content_id,
                ContentItem.module == "SPEAKING",
                ContentItem.kind == "SPEAKING_LESSON",
                ContentItem.slot == "CORE",
                ContentItem.status == "PUBLISHED",
                ContentItem.cycle == LearningPlan.cycle,
                ContentItem.day == ModuleProgress.current_day,
                ContentItem.cefr_level == ModuleProgress.cefr_level,
                ContentItem.goal_variant == ModuleProgress.goal_variant,
            )
            .with_for_update(read=True, of=ContentItem)
        )
        today = await SpeakingQueryService(self.session).get_today(user_id)
        if today.activity is None:
            raise ConflictError(
                "Speaking is already completed.", code="ACTIVITY_ALREADY_COMPLETED"
            )
        # Check credits even for a stale request for a previously completed day.
        credited = await self.session.scalar(
            select(ActivityCompletion.id).where(
                ActivityCompletion.user_id == user_id,
                ActivityCompletion.module_progress_id == today.module_progress_id,
                ActivityCompletion.content_item_id == content_id,
            )
        )
        if credited is not None:
            raise ConflictError(
                "This activity has already been completed.",
                code="ACTIVITY_ALREADY_COMPLETED",
            )
        if content_id != today.activity.id:
            raise ConflictError(
                "Choose the currently assigned speaking activity.",
                code="ACTIVITY_NOT_CURRENT",
            )
        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.module_progress_id == today.module_progress_id,
                PracticeSubmission.content_item_id == content_id,
                PracticeSubmission.mode == "RECORDED_SPEAKING",
                PracticeSubmission.status == "DRAFT",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if prior is not None and (draft is None or prior.submission_id != draft.id):
            raise ConflictError(
                "The original draft is no longer active. Use a new key for a new draft.",
                code="DRAFT_NO_LONGER_ACTIVE",
            )
        created = draft is None
        if draft is None:
            draft = PracticeSubmission(
                id=uuid4(),
                user_id=user_id,
                module_progress_id=today.module_progress_id,
                content_item_id=content_id,
                mode="RECORDED_SPEAKING",
                status="DRAFT",
                evaluation_status="NOT_REQUIRED",
                revision_number=1,
                input={},
            )
            self.session.add(draft)
            await self.session.flush()
        if prior is None:
            self.session.add(
                SpeakingDraftRequest(
                    user_id=user_id,
                    key_hash=key_hash,
                    content_item_id=content_id,
                    submission_id=draft.id,
                )
            )
        result = SpeakingDraftResponse(
            submission_id=draft.id,
            mode=draft.mode,
            status=draft.status,
            evaluation_status=draft.evaluation_status,
            content_item_id=draft.content_item_id,
            media_upload_id=draft.media_upload_id,
            created_at=draft.created_at,
        )
        return result, created
