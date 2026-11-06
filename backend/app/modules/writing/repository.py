"""Read-only queries for daily writing prompt resolution and active draft lookup."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import ContentItem
from app.modules.learning.models import ModuleProgress
from app.modules.learning.repository import today_plan_statement
from app.modules.practice.models import PracticeSubmission


def writing_today_statement(user_id: UUID):
    draft_id = (
        select(PracticeSubmission.id)
        .where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.module_progress_id == ModuleProgress.id,
            PracticeSubmission.content_item_id == ContentItem.id,
            PracticeSubmission.mode == "WRITING",
            PracticeSubmission.status == "DRAFT",
            PracticeSubmission.revision_number == 1,
        )
        .order_by(PracticeSubmission.created_at.desc(), PracticeSubmission.id.desc())
        .limit(1)
        .correlate(ModuleProgress, ContentItem)
        .scalar_subquery()
    )
    return today_plan_statement(user_id).add_columns(
        ContentItem.body["writing_type"].label("writing_type"),
        ContentItem.body["instructions"].label("instructions"),
        ContentItem.body["target_word_count"].label("target_word_count"),
        ContentItem.body["minimum_word_count"].label("minimum_word_count"),
        ContentItem.body["maximum_word_count"].label("maximum_word_count"),
        ContentItem.body["time_limit_minutes"].label("time_limit_minutes"),
        ContentItem.body["tips"].label("tips"),
        draft_id.label("existing_draft_id"),
    )


class WritingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def today(self, user_id: UUID):
        return (await self.session.execute(writing_today_statement(user_id))).all()

