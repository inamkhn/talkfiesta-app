"""Read a plan and credited module days in a single database snapshot."""

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.practice.models import PracticeSubmission


def timeline_statement(user_id: UUID, module: str):
    credited_item = (
        select(ActivityCompletion.id)
        .where(
            ActivityCompletion.user_id == user_id,
            ActivityCompletion.module_progress_id == ModuleProgress.id,
            ActivityCompletion.content_item_id == ContentItem.id,
        )
        .correlate(ModuleProgress, ContentItem)
        .exists()
    )
    return (
        current_plan_statement(user_id)
        .outerjoin(
            ContentItem,
            and_(
                ModuleProgress.module == module,
                ContentItem.release_key == ModuleProgress.content_release,
                ContentItem.module == ModuleProgress.module,
                ContentItem.kind == ModuleProgress.module + "_LESSON",
                ContentItem.cycle == LearningPlan.cycle,
                ContentItem.day.between(1, 21),
                ContentItem.cefr_level == ModuleProgress.cefr_level,
                ContentItem.goal_variant == ModuleProgress.goal_variant,
                ContentItem.slot == "CORE",
                or_(
                    ContentItem.status == "PUBLISHED",
                    and_(ContentItem.status == "ARCHIVED", credited_item),
                ),
            ),
        )
        .outerjoin(
            ActivityCompletion,
            and_(
                ActivityCompletion.user_id == user_id,
                ActivityCompletion.module_progress_id == ModuleProgress.id,
                ActivityCompletion.content_item_id == ContentItem.id,
            ),
        )
        .add_columns(
            ContentItem.day.label("content_day"),
            ContentItem.title,
            ContentItem.status.label("content_status"),
            ActivityCompletion.completed_at.label("credited_at"),
        )
    )


def today_plan_statement(user_id: UUID):
    has_draft = (
        select(PracticeSubmission.id)
        .where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.module_progress_id == ModuleProgress.id,
            PracticeSubmission.content_item_id == ContentItem.id,
            PracticeSubmission.status == "DRAFT",
            PracticeSubmission.mode.in_(("RECORDED_SPEAKING", "WRITING", "VOCAB_QUIZ")),
        )
        .correlate(ModuleProgress, ContentItem)
        .exists()
    )
    return (
        current_plan_statement(user_id)
        .outerjoin(
            ContentItem,
            and_(
                ModuleProgress.status == "ACTIVE",
                ContentItem.release_key == ModuleProgress.content_release,
                ContentItem.module == ModuleProgress.module,
                ContentItem.kind == ModuleProgress.module + "_LESSON",
                ContentItem.cycle == LearningPlan.cycle,
                ContentItem.day == ModuleProgress.current_day,
                ContentItem.cefr_level == ModuleProgress.cefr_level,
                ContentItem.goal_variant == ModuleProgress.goal_variant,
                ContentItem.slot == "CORE",
                ContentItem.status == "PUBLISHED",
            ),
        )
        .add_columns(
            User.timezone,
            ContentItem.id.label("content_item_id"),
            ContentItem.kind.label("content_kind"),
            ContentItem.title,
            ContentItem.body["description"].label("description"),
            ContentItem.body["estimated_minutes"].label("estimated_minutes"),
            has_draft.label("has_draft"),
        )
    )


def current_plan_statement(user_id: UUID):
    credited_days = (
        select(func.count(func.distinct(ContentItem.day)))
        .select_from(ActivityCompletion)
        .join(ContentItem, ContentItem.id == ActivityCompletion.content_item_id)
        .where(
            ActivityCompletion.user_id == user_id,
            ActivityCompletion.module_progress_id == ModuleProgress.id,
            ContentItem.release_key == ModuleProgress.content_release,
            ContentItem.module == ModuleProgress.module,
            ContentItem.kind == ModuleProgress.module + "_LESSON",
            ContentItem.cycle == LearningPlan.cycle,
            ContentItem.cefr_level == ModuleProgress.cefr_level,
            ContentItem.goal_variant == ModuleProgress.goal_variant,
            ContentItem.slot == "CORE",
            ContentItem.day.between(1, 21),
            ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
        )
        .correlate(ModuleProgress, LearningPlan)
        .scalar_subquery()
    )
    return (
        select(
            User.onboarding_status,
            LearningPlan,
            ModuleProgress,
            credited_days.label("completed_days"),
        )
        .select_from(User)
        .outerjoin(
            LearningPlan,
            and_(LearningPlan.user_id == User.id, LearningPlan.status == "ACTIVE"),
        )
        .outerjoin(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
        .where(User.id == user_id)
        .execution_options(populate_existing=True)
    )


class LearningPlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def current(self, user_id: UUID):
        return (await self.session.execute(current_plan_statement(user_id))).all()

    async def today(self, user_id: UUID):
        return (await self.session.execute(today_plan_statement(user_id))).all()

    async def timeline(self, user_id: UUID, module: str):
        return (await self.session.execute(timeline_statement(user_id, module))).all()
