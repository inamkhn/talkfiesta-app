"""Owner-scoped onboarding persistence; services own transactions."""

from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assessment.models import AssessmentAttempt
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.learning.models import LearningPlan, ModuleProgress


class OnboardingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_assessment(
        self, user_id: UUID, attempt_id: UUID
    ) -> AssessmentAttempt | None:
        return await self._session.scalar(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.user_id == user_id,
            )
            .with_for_update()
        )

    async def get_first_plan(self, user_id: UUID) -> LearningPlan | None:
        return await self._session.scalar(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id)
            .order_by(LearningPlan.created_at, LearningPlan.id)
            .limit(1)
        )

    async def get_modules(self, plan_id: UUID) -> list[ModuleProgress]:
        return list(
            await self._session.scalars(
                select(ModuleProgress).where(ModuleProgress.learning_plan_id == plan_id)
            )
        )

    async def curriculum(self, cefr: str, goals: list[str]) -> list[ContentItem]:
        return list(
            await self._session.scalars(
                select(ContentItem)
                .where(
                    ContentItem.status == "PUBLISHED",
                    ContentItem.cycle == 1,
                    ContentItem.slot == "CORE",
                    ContentItem.cefr_level == cefr,
                    ContentItem.goal_variant.in_(goals),
                    ContentItem.kind.in_(
                        ("SPEAKING_LESSON", "VOCABULARY_LESSON", "WRITING_LESSON")
                    ),
                )
                .order_by(
                    ContentItem.published_at.desc().nulls_last(),
                    ContentItem.release_key,
                    ContentItem.id,
                )
                .with_for_update(read=True)
            )
        )

    async def published_words(self, ids: set[UUID]) -> set[UUID]:
        if not ids:
            return set()
        return set(
            await self._session.scalars(
                select(ContentItem.id)
                .where(
                    ContentItem.id.in_(ids),
                    ContentItem.kind == "VOCAB_WORD",
                    ContentItem.status == "PUBLISHED",
                )
                .order_by(ContentItem.id)
                .with_for_update(read=True)
            )
        )

    def add_plan(self, plan: LearningPlan, modules: list[ModuleProgress]) -> None:
        self._session.add_all([plan, *modules])

    async def read_state(
        self, user_id: UUID
    ) -> tuple[User, AssessmentAttempt | None] | None:
        # Read user and selected initial attempt in one statement/snapshot.
        # An active attempt wins over historical completed/failed attempts.
        active = AssessmentAttempt.status.in_(
            ("IN_PROGRESS", "SUBMITTED", "PROCESSING", "FAILED_RETRYABLE")
        )
        attempt_id = (
            select(AssessmentAttempt.id)
            .where(
                AssessmentAttempt.user_id == User.id,
                AssessmentAttempt.kind == "INITIAL",
            )
            .order_by(
                case((active, 0), else_=1),
                AssessmentAttempt.started_at.desc(),
                AssessmentAttempt.id.desc(),
            )
            .limit(1)
            .correlate(User)
            .scalar_subquery()
        )
        result = await self._session.execute(
            select(User, AssessmentAttempt)
            .outerjoin(AssessmentAttempt, AssessmentAttempt.id == attempt_id)
            .where(User.id == user_id)
            .execution_options(populate_existing=True)
        )
        row = result.one_or_none()
        return (row[0], row[1]) if row is not None else None

    async def lock_user(self, user_id: UUID) -> User | None:
        return await self._session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
