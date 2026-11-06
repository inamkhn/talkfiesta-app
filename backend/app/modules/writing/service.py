"""Read-only daily writing assignment resolution."""

from __future__ import annotations

import logging
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.modules.learning.service import LearningPlanQueryService
from app.modules.writing.repository import WritingRepository
from app.modules.writing.schemas import WritingPrompt, WritingTodayResponse

logger = logging.getLogger(__name__)


class WritingQueryService:
    def __init__(self, session: AsyncSession):
        self.repository = WritingRepository(session)
        self.learning = LearningPlanQueryService(session)

    async def get_today(self, user_id: UUID) -> WritingTodayResponse:
        rows = await self.repository.today(user_id)
        current = self.learning.current_response(user_id, rows)
        progress = next(
            (item for item in current.modules if item.module == "WRITING"), None
        )
        if progress is None:
            raise NotFoundError(
                "Writing is not enrolled in the active plan.",
                code="MODULE_NOT_ENROLLED",
            )
        if progress.status == "COMPLETED":
            return WritingTodayResponse(
                cycle=current.plan.cycle,
                day=21,
                module_progress_id=progress.progress_id,
                module_status="COMPLETED",
                prompt=None,
                existing_draft_id=None,
            )

        row = next(r for r in rows if r.ModuleProgress.id == progress.progress_id)
        if progress.status != "ACTIVE" or row.content_item_id is None:
            raise ConflictError(
                "The required writing curriculum content is not available.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )

        try:
            prompt = WritingPrompt(
                id=row.content_item_id,
                kind=row.content_kind,
                title=row.title,
                writing_type=row.writing_type,
                instructions=row.instructions,
                target_word_count=row.target_word_count,
                minimum_word_count=row.minimum_word_count,
                maximum_word_count=row.maximum_word_count,
                time_limit_minutes=row.time_limit_minutes,
                tips=row.tips,
            )
            return WritingTodayResponse(
                cycle=current.plan.cycle,
                day=progress.current_day,
                module_progress_id=progress.progress_id,
                module_status="ACTIVE",
                prompt=prompt,
                existing_draft_id=row.existing_draft_id,
            )
        except ValidationError:
            logger.error(
                "writing_lesson_inconsistent user_id=%s content_item_id=%s",
                user_id,
                row.content_item_id,
            )
            raise ServiceUnavailableError(
                "The saved writing lesson is incomplete. Please try again later.",
                code="WRITING_LESSON_UNAVAILABLE",
            ) from None

