"""Read-only speaking assignment resolution."""

import logging
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.modules.learning.service import LearningPlanQueryService
from app.modules.speaking.repository import SpeakingRepository
from app.modules.speaking.schemas import SpeakingActivity, SpeakingTodayResponse

logger = logging.getLogger(__name__)


class SpeakingQueryService:
    def __init__(self, session: AsyncSession):
        self.repository = SpeakingRepository(session)
        self.learning = LearningPlanQueryService(session)

    async def get_today(self, user_id: UUID) -> SpeakingTodayResponse:
        rows = await self.repository.today(user_id)
        current = self.learning.current_response(user_id, rows)
        progress = next(
            (item for item in current.modules if item.module == "SPEAKING"), None
        )
        if progress is None:
            raise NotFoundError(
                "Speaking is not enrolled in the active plan.",
                code="MODULE_NOT_ENROLLED",
            )
        if progress.status == "COMPLETED":
            return SpeakingTodayResponse(
                plan_id=current.plan.id,
                module_progress_id=progress.progress_id,
                cycle=current.plan.cycle,
                day=21,
                module_status="COMPLETED",
                activity=None,
            )
        row = next(row for row in rows if row.ModuleProgress.id == progress.progress_id)
        if progress.status != "ACTIVE" or row.content_item_id is None:
            raise ConflictError(
                "The required speaking curriculum content is not available.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )
        try:
            activity = SpeakingActivity(
                id=row.content_item_id,
                kind=row.content_kind,
                title=row.title,
                exercise_type=row.exercise_type,
                topic=row.topic,
                instructions=row.instructions,
                target_duration_seconds=row.target_duration_seconds,
                target_cefr=progress.target_cefr,
                preparation_seconds=row.preparation_seconds,
                tips=row.tips,
            )
            return SpeakingTodayResponse(
                plan_id=current.plan.id,
                module_progress_id=progress.progress_id,
                cycle=current.plan.cycle,
                day=progress.current_day,
                module_status="ACTIVE",
                activity=activity,
                existing_draft_id=row.existing_draft_id,
            )
        except ValidationError:
            logger.error(
                "speaking_lesson_inconsistent user_id=%s content_item_id=%s",
                user_id,
                row.content_item_id,
            )
            raise ServiceUnavailableError(
                "The saved speaking lesson is incomplete. Please try again later.",
                code="SPEAKING_LESSON_UNAVAILABLE",
            ) from None
