"""Dashboard aggregates in the same snapshot as the pinned next lessons."""

from uuid import UUID

from sqlalchemy import Date, Integer, cast, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.gamification.models import UserAchievement
from app.modules.learning.models import ActivityCompletion
from app.modules.learning.repository import today_plan_statement
from app.modules.practice.models import PracticeSubmission
from app.modules.vocabulary.models import UserVocabulary


def dashboard_statement(user_id: UUID):
    timezone = select(User.timezone).where(User.id == user_id).scalar_subquery()
    today = cast(func.timezone(timezone, func.current_timestamp()), Date)
    dates = (
        select(ActivityCompletion.local_practice_date.label("day"))
        .where(ActivityCompletion.user_id == user_id)
        .distinct()
        .cte("practice_dates")
    )
    islands = (
        select(
            dates.c.day,
            (
                dates.c.day
                - cast(func.row_number().over(order_by=dates.c.day), Integer)
            ).label("island"),
        )
        .where(dates.c.day <= today)
        .cte("streak_dates")
    )
    streaks = (
        select(
            func.max(islands.c.day).label("last_day"),
            func.count().label("length"),
        )
        .group_by(islands.c.island)
        .cte("streaks")
    )
    pending_filter = (
        PracticeSubmission.user_id == user_id,
        PracticeSubmission.status == "ACCEPTED",
        PracticeSubmission.evaluation_status.in_(("PENDING", "PROCESSING")),
    )
    pending = (
        select(
            PracticeSubmission.id,
            PracticeSubmission.mode,
            PracticeSubmission.evaluation_status,
            PracticeSubmission.submitted_at,
        )
        .where(*pending_filter)
        .order_by(
            PracticeSubmission.submitted_at.desc().nulls_last(),
            PracticeSubmission.id.desc(),
        )
        .limit(5)
        .subquery()
    )
    achievements = (
        select(
            UserAchievement.id,
            UserAchievement.achievement_key,
            UserAchievement.earned_at,
        )
        .where(UserAchievement.user_id == user_id)
        .order_by(UserAchievement.earned_at.desc(), UserAchievement.id.desc())
        .limit(5)
        .subquery()
    )
    # JSON contains only explicitly selected public fields; input/feedback/context
    # are deliberately never loaded. Ordered subqueries cap both result lists.
    pending_json = select(
        func.json_agg(
            aggregate_order_by(
                func.json_build_object(
                    "submission_id",
                    pending.c.id,
                    "mode",
                    pending.c.mode,
                    "evaluation_status",
                    pending.c.evaluation_status,
                    "submitted_at",
                    pending.c.submitted_at,
                ),
                pending.c.submitted_at.desc().nulls_last(),
                pending.c.id.desc(),
            )
        )
    ).scalar_subquery()
    achievements_json = select(
        func.json_agg(
            aggregate_order_by(
                func.json_build_object(
                    "achievement_key",
                    achievements.c.achievement_key,
                    "earned_at",
                    achievements.c.earned_at,
                ),
                achievements.c.earned_at.desc(),
                achievements.c.id.desc(),
            )
        )
    ).scalar_subquery()
    return today_plan_statement(user_id).add_columns(
        User.display_name,
        select(func.coalesce(func.sum(ActivityCompletion.duration_seconds), 0))
        .where(ActivityCompletion.user_id == user_id)
        .scalar_subquery()
        .label("total_seconds"),
        select(func.coalesce(func.sum(ActivityCompletion.duration_seconds), 0))
        .where(
            ActivityCompletion.user_id == user_id,
            ActivityCompletion.local_practice_date == today,
        )
        .scalar_subquery()
        .label("today_seconds"),
        select(func.count())
        .select_from(UserVocabulary)
        .where(UserVocabulary.user_id == user_id, UserVocabulary.status == "MASTERED")
        .scalar_subquery()
        .label("mastered_words"),
        select(func.coalesce(func.max(streaks.c.length), 0))
        .scalar_subquery()
        .label("longest_days"),
        select(func.coalesce(func.max(streaks.c.length), 0))
        .where(streaks.c.last_day.between(today - 1, today))
        .scalar_subquery()
        .label("current_days"),
        select(func.max(dates.c.day)).scalar_subquery().label("last_active_local_date"),
        select(func.count())
        .select_from(PracticeSubmission)
        .where(*pending_filter)
        .scalar_subquery()
        .label("pending_feedback_count"),
        pending_json.label("pending_feedback"),
        achievements_json.label("recent_achievements"),
    )


class DashboardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def overview(self, user_id: UUID):
        return (await self.session.execute(dashboard_statement(user_id))).all()
