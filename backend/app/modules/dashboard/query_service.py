"""Build a dashboard from one owner-scoped database snapshot."""

import json
import logging
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    DashboardModule,
    DashboardPlan,
    DashboardResponse,
    LearnerSummary,
    PendingFeedback,
    PracticeSummary,
    RecentAchievement,
    StreakSummary,
    TodayPreview,
)
from app.modules.learning.service import LearningPlanQueryService

logger = logging.getLogger(__name__)
MODE_MODULE = {
    "RECORDED_SPEAKING": "SPEAKING",
    "PRONUNCIATION": "SPEAKING",
    "WRITING": "WRITING",
    "VOCAB_QUIZ": "VOCABULARY",
    "VOCAB_REVIEW": "VOCABULARY",
}


class DashboardQueryService:
    def __init__(self, session: AsyncSession):
        self.repository = DashboardRepository(session)
        self.learning = LearningPlanQueryService(session)

    async def get_overview(self, user_id: UUID) -> DashboardResponse:
        rows = await self.repository.overview(user_id)
        today = self.learning.today_response(user_id, rows)
        current = self.learning.current_response(user_id, rows)
        row = rows[0]
        completed = sum(module.completed_days for module in current.modules)
        total = 21 * len(current.modules)
        try:
            pending = [
                PendingFeedback.model_validate_json(
                    json.dumps(
                        {
                            "submission_id": item["submission_id"],
                            "module": MODE_MODULE[item["mode"]],
                            "evaluation_status": item["evaluation_status"],
                            "submitted_at": item["submitted_at"],
                        }
                    )
                )
                for item in row.pending_feedback or []
            ]
            return DashboardResponse(
                learner=LearnerSummary(
                    display_name=row.display_name,
                    timezone=today.timezone,
                    provisional_cefr=current.plan.placement_cefr,
                ),
                learning_plan=DashboardPlan(
                    id=current.plan.id,
                    cycle=current.plan.cycle,
                    daily_target_minutes=current.plan.daily_target_minutes,
                    completed_required_activities=completed,
                    total_required_activities=total,
                    overall_completion_percent=round(completed / total * 100, 1),
                ),
                modules=[
                    DashboardModule(
                        module=module.module,
                        completed_days=module.completed_days,
                        current_day=module.current_day,
                    )
                    for module in current.modules
                ],
                streak=StreakSummary(
                    current_days=row.current_days,
                    longest_days=row.longest_days,
                    last_active_local_date=row.last_active_local_date,
                ),
                practice=PracticeSummary(
                    total_seconds=row.total_seconds,
                    today_seconds=row.today_seconds,
                    mastered_words=row.mastered_words,
                ),
                today_preview=[
                    TodayPreview(
                        module=item.module,
                        day=item.day,
                        title=item.title,
                        content_item_id=item.content_item_id,
                    )
                    for item in today.activities
                ],
                pending_feedback=pending,
                pending_feedback_count=row.pending_feedback_count,
                recent_achievements=[
                    RecentAchievement.model_validate_json(json.dumps(item))
                    for item in row.recent_achievements or []
                ],
            )
        except (ValidationError, KeyError, TypeError):
            logger.error("dashboard_inconsistent user_id=%s", user_id)
            raise ServiceUnavailableError(
                "The saved dashboard data is incomplete. Please try again later.",
                code="DASHBOARD_UNAVAILABLE",
            ) from None
