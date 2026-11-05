"""Read the assigned speaking lesson and owned draft in one snapshot."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import ContentItem
from app.modules.learning.models import ModuleProgress
from app.modules.learning.repository import today_plan_statement
from app.modules.practice.models import PracticeSubmission


def speaking_today_statement(user_id: UUID):
    draft_id = (
        select(PracticeSubmission.id)
        .where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.module_progress_id == ModuleProgress.id,
            PracticeSubmission.content_item_id == ContentItem.id,
            PracticeSubmission.mode == "RECORDED_SPEAKING",
            PracticeSubmission.status == "DRAFT",
        )
        .order_by(PracticeSubmission.created_at.desc(), PracticeSubmission.id.desc())
        .limit(1)
        .correlate(ModuleProgress, ContentItem)
        .scalar_subquery()
    )
    return today_plan_statement(user_id).add_columns(
        ContentItem.body["exercise_type"].label("exercise_type"),
        ContentItem.body["topic"].label("topic"),
        ContentItem.body["instructions"].label("instructions"),
        ContentItem.body["target_duration_seconds"].label("target_duration_seconds"),
        ContentItem.body["preparation_seconds"].label("preparation_seconds"),
        ContentItem.body["tips"].label("tips"),
        draft_id.label("existing_draft_id"),
    )


class SpeakingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def today(self, user_id: UUID):
        return (await self.session.execute(speaking_today_statement(user_id))).all()
