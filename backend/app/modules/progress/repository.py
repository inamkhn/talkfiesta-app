"""Read-only database queries for progress, streaks, calendar, trends, and history."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assessment.models import AssessmentAttempt
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.gamification.models import UserAchievement
from app.modules.jobs.models import AiJob
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.learning.repository import current_plan_statement
from app.modules.practice.models import PracticeSubmission
from app.modules.vocabulary.models import UserVocabulary


class ProgressRepository:
    """Owner-scoped read queries for `/api/v1/progress`."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_state(self, user_id: UUID) -> tuple[str, str] | None:
        """Return `(onboarding_status, timezone)` for `user_id`, or `None`."""
        stmt = select(User.onboarding_status, User.timezone).where(User.id == user_id)
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        return str(row.onboarding_status), str(row.timezone or "UTC")

    async def get_active_plan_rows(self, user_id: UUID):
        """Return user onboarding/timezone + active plan + module progress + CORE completed_days."""
        stmt = current_plan_statement(user_id).add_columns(User.timezone)
        result = await self.session.execute(stmt)
        return result.all()

    async def get_credited_dates(self, user_id: UUID) -> set[date]:
        """Return all distinct `local_practice_date` values for `user_id`."""
        stmt = (
            select(ActivityCompletion.local_practice_date)
            .where(ActivityCompletion.user_id == user_id)
            .distinct()
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def get_practice_totals(
        self,
        user_id: UUID,
        *,
        plan_id: UUID | None = None,
    ) -> tuple[int, int]:
        """Return `(total_seconds, active_days)` for `user_id` (optionally scoped to `plan_id`)."""
        stmt = select(
            func.coalesce(func.sum(ActivityCompletion.duration_seconds), 0).label(
                "total_seconds"
            ),
            func.count(func.distinct(ActivityCompletion.local_practice_date)).label(
                "active_days"
            ),
        ).where(ActivityCompletion.user_id == user_id)

        if plan_id is not None:
            stmt = stmt.join(
                ModuleProgress,
                ModuleProgress.id == ActivityCompletion.module_progress_id,
            ).where(ModuleProgress.learning_plan_id == plan_id)

        row = (await self.session.execute(stmt)).one()
        return int(row.total_seconds or 0), int(row.active_days or 0)

    async def get_vocabulary_counts(
        self, user_id: UUID, now: datetime
    ) -> dict[str, int]:
        """Return counts of `learning`, `reviewing`, `mastered`, and `due_now` words."""
        stmt = select(
            func.coalesce(
                func.sum(case((UserVocabulary.status == "LEARNING", 1), else_=0)), 0
            ).label("learning"),
            func.coalesce(
                func.sum(case((UserVocabulary.status == "REVIEWING", 1), else_=0)), 0
            ).label("reviewing"),
            func.coalesce(
                func.sum(case((UserVocabulary.status == "MASTERED", 1), else_=0)), 0
            ).label("mastered"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            UserVocabulary.status.in_(("LEARNING", "REVIEWING"))
                            & UserVocabulary.next_review_at.is_not(None)
                            & (UserVocabulary.next_review_at <= now),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("due_now"),
        ).where(UserVocabulary.user_id == user_id)

        row = (await self.session.execute(stmt)).one()
        return {
            "learning": int(row.learning or 0),
            "reviewing": int(row.reviewing or 0),
            "mastered": int(row.mastered or 0),
            "due_now": int(row.due_now or 0),
        }

    async def get_ai_feedback_counts(
        self,
        user_id: UUID,
        *,
        plan_id: UUID | None = None,
    ) -> tuple[int, int]:
        """Return `(pending_count, completed_count)` for accepted submissions."""
        stmt = select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            PracticeSubmission.evaluation_status.in_(
                                ("PENDING", "PROCESSING")
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("pending_count"),
            func.coalesce(
                func.sum(
                    case(
                        (PracticeSubmission.evaluation_status == "COMPLETED", 1),
                        else_=0,
                    )
                ),
                0,
            ).label("completed_count"),
        ).where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.status == "ACCEPTED",
        )

        if plan_id is not None:
            stmt = stmt.join(
                ModuleProgress,
                ModuleProgress.id == PracticeSubmission.module_progress_id,
            ).where(ModuleProgress.learning_plan_id == plan_id)

        row = (await self.session.execute(stmt)).one()
        return int(row.pending_count or 0), int(row.completed_count or 0)

    async def get_plan_and_module_progress(
        self,
        user_id: UUID,
        module: str,
        *,
        cycle: int | None = None,
    ):
        """Return `(user, plan, module_progress, completed_days)` for `user_id`."""
        user = await self.session.scalar(select(User).where(User.id == user_id))
        if user is None:
            return None, None, None, 0

        plan_stmt = select(LearningPlan).where(LearningPlan.user_id == user_id)
        if cycle is None:
            plan_stmt = plan_stmt.where(LearningPlan.status == "ACTIVE")
        else:
            plan_stmt = plan_stmt.where(LearningPlan.cycle == cycle).order_by(
                LearningPlan.created_at.desc(), LearningPlan.id.desc()
            )
        plan = await self.session.scalar(plan_stmt.limit(1))
        if plan is None:
            return user, None, None, 0

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
                ContentItem.cycle == plan.cycle,
                ContentItem.cefr_level == ModuleProgress.cefr_level,
                ContentItem.goal_variant == ModuleProgress.goal_variant,
                ContentItem.slot == "CORE",
                ContentItem.day.between(1, 21),
                ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
            )
            .correlate(ModuleProgress)
            .scalar_subquery()
        )

        mp_stmt = select(
            ModuleProgress,
            credited_days.label("completed_days"),
        ).where(
            ModuleProgress.learning_plan_id == plan.id,
            ModuleProgress.module == module,
        )
        row = (await self.session.execute(mp_stmt)).first()
        if row is None:
            return user, plan, None, 0
        return user, plan, row.ModuleProgress, int(row.completed_days or 0)

    async def get_module_submissions(
        self,
        user_id: UUID,
        module_progress_id: UUID,
        mode: str,
    ):
        """Return accepted submissions for `module_progress_id` and `mode` ordered newest-first."""
        latest_job_rubric = (
            select(AiJob.rubric_version)
            .where(
                AiJob.practice_submission_id == PracticeSubmission.id,
                AiJob.status == "SUCCEEDED",
            )
            .order_by(AiJob.finished_at.desc().nulls_last(), AiJob.id.desc())
            .limit(1)
            .correlate(PracticeSubmission)
            .scalar_subquery()
        )
        stmt = (
            select(
                PracticeSubmission,
                ContentItem.day.label("content_day"),
                latest_job_rubric.label("job_rubric_version"),
            )
            .join(ContentItem, ContentItem.id == PracticeSubmission.content_item_id)
            .where(
                and_(
                    PracticeSubmission.user_id == user_id,
                    PracticeSubmission.module_progress_id == module_progress_id,
                    PracticeSubmission.mode == mode,
                    PracticeSubmission.status == "ACCEPTED",
                )
            )
            .order_by(
                PracticeSubmission.submitted_at.desc().nulls_last(),
                PracticeSubmission.id.desc(),
            )
        )
        return (await self.session.execute(stmt)).all()

    async def get_activity_calendar_rows(
        self,
        user_id: UUID,
        date_from: date,
        date_to: date,
        *,
        module: str | None = None,
    ):
        """Return `(local_practice_date, module, completion_count, practice_seconds)` grouped by day & module."""
        stmt = (
            select(
                ActivityCompletion.local_practice_date.label("practice_date"),
                ModuleProgress.module.label("module"),
                func.count(ActivityCompletion.id).label("completion_count"),
                func.coalesce(func.sum(ActivityCompletion.duration_seconds), 0).label(
                    "practice_seconds"
                ),
            )
            .join(
                ModuleProgress,
                ModuleProgress.id == ActivityCompletion.module_progress_id,
            )
            .where(
                ActivityCompletion.user_id == user_id,
                ActivityCompletion.local_practice_date.between(date_from, date_to),
            )
        )
        if module is not None:
            stmt = stmt.where(ModuleProgress.module == module)

        stmt = stmt.group_by(
            ActivityCompletion.local_practice_date,
            ModuleProgress.module,
        ).order_by(ActivityCompletion.local_practice_date.asc())
        return (await self.session.execute(stmt)).all()

    async def get_user_achievements(self, user_id: UUID) -> list[UserAchievement]:
        """Return all `UserAchievement` rows for `user_id` ordered by `earned_at`."""
        stmt = (
            select(UserAchievement)
            .where(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.earned_at.asc(), UserAchievement.id.asc())
        )
        return list((await self.session.scalars(stmt)).all())

    async def count_module_completions(self, user_id: UUID, module: str) -> int:
        """Return total credited `ActivityCompletion` rows for `user_id` in `module`."""
        stmt = (
            select(func.count(ActivityCompletion.id))
            .join(
                ModuleProgress,
                ModuleProgress.id == ActivityCompletion.module_progress_id,
            )
            .where(
                ActivityCompletion.user_id == user_id,
                ModuleProgress.module == module,
            )
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def get_completed_submissions_for_badges(self, user_id: UUID):
        """Return accepted, completed submissions + latest job rubric for badge checks."""
        latest_job_rubric = (
            select(AiJob.rubric_version)
            .where(
                AiJob.practice_submission_id == PracticeSubmission.id,
                AiJob.status == "SUCCEEDED",
            )
            .order_by(AiJob.finished_at.desc().nulls_last(), AiJob.id.desc())
            .limit(1)
            .correlate(PracticeSubmission)
            .scalar_subquery()
        )
        stmt = select(
            PracticeSubmission,
            latest_job_rubric.label("job_rubric_version"),
        ).where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.status == "ACCEPTED",
            PracticeSubmission.evaluation_status == "COMPLETED",
        )
        return (await self.session.execute(stmt)).all()

    async def get_cycle_completion_progress(
        self, user_id: UUID
    ) -> tuple[bool, int, int]:
        """Return `(any_cycle_fully_completed, active_current_activities, active_target_activities)`."""
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
        stmt = (
            select(
                LearningPlan.id.label("plan_id"),
                LearningPlan.status.label("plan_status"),
                ModuleProgress.id.label("progress_id"),
                credited_days.label("completed_days"),
            )
            .join(
                ModuleProgress,
                ModuleProgress.learning_plan_id == LearningPlan.id,
            )
            .where(LearningPlan.user_id == user_id)
        )
        rows = (await self.session.execute(stmt)).all()
        if not rows:
            return False, 0, 63

        by_plan: dict[UUID, list[tuple[str, int]]] = {}
        for row in rows:
            days = min(max(int(row.completed_days or 0), 0), 21)
            by_plan.setdefault(row.plan_id, []).append((row.plan_status, days))

        any_completed = False
        active_current = 0
        active_target = 63
        best_current = 0
        best_target = 63

        for enrollments in by_plan.values():
            if not enrollments:
                continue
            plan_status = enrollments[0][0]
            total_req = 21 * len(enrollments)
            total_done = sum(d for _, d in enrollments)
            if all(d >= 21 for _, d in enrollments):
                any_completed = True
            if plan_status == "ACTIVE":
                active_current = total_done
                active_target = total_req
            if total_done > best_current:
                best_current = total_done
                best_target = total_req

        if active_current == 0 and best_current > 0:
            return any_completed, best_current, best_target
        return any_completed, active_current, active_target

    async def get_trend_submissions(
        self,
        user_id: UUID,
        mode: str,
        *,
        baseline_only: bool = False,
    ):
        """Return accepted submissions for `user_id` and `mode` ordered oldest-first."""
        latest_job_rubric = (
            select(AiJob.rubric_version)
            .where(
                AiJob.practice_submission_id == PracticeSubmission.id,
                AiJob.status == "SUCCEEDED",
            )
            .order_by(AiJob.finished_at.desc().nulls_last(), AiJob.id.desc())
            .limit(1)
            .correlate(PracticeSubmission)
            .scalar_subquery()
        )
        stmt = select(
            PracticeSubmission,
            latest_job_rubric.label("job_rubric_version"),
        ).where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.mode == mode,
            PracticeSubmission.status == "ACCEPTED",
        )
        if baseline_only:
            stmt = stmt.where(PracticeSubmission.revision_number == 1)
        stmt = stmt.order_by(
            PracticeSubmission.submitted_at.asc().nulls_last(),
            PracticeSubmission.created_at.asc(),
            PracticeSubmission.id.asc(),
        )
        return (await self.session.execute(stmt)).all()

    async def get_mastered_vocabulary_timestamps(
        self, user_id: UUID
    ) -> list[datetime]:
        """Return non-null `mastered_at` timestamps for `user_id` ordered ascending."""
        stmt = (
            select(UserVocabulary.mastered_at)
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.mastered_at.is_not(None),
            )
            .order_by(UserVocabulary.mastered_at.asc(), UserVocabulary.id.asc())
        )
        return [
            ts
            for ts in (await self.session.scalars(stmt)).all()
            if ts is not None
        ]

    async def get_activity_history_rows(
        self,
        user_id: UUID,
        *,
        module: str | None = None,
        cursor_completed_at: datetime | None = None,
        cursor_id: UUID | None = None,
        limit: int = 20,
    ):
        """Return credited activity completions joined with module, plan, content, and submission."""
        stmt = (
            select(
                ActivityCompletion,
                ModuleProgress.module.label("module"),
                LearningPlan.cycle.label("cycle"),
                ContentItem.day.label("content_day"),
                ContentItem.title.label("content_title"),
                PracticeSubmission,
            )
            .join(
                ModuleProgress,
                ModuleProgress.id == ActivityCompletion.module_progress_id,
            )
            .join(
                LearningPlan,
                LearningPlan.id == ModuleProgress.learning_plan_id,
            )
            .join(
                ContentItem,
                ContentItem.id == ActivityCompletion.content_item_id,
            )
            .outerjoin(
                PracticeSubmission,
                and_(
                    PracticeSubmission.id
                    == ActivityCompletion.source_submission_id,
                    PracticeSubmission.user_id == user_id,
                ),
            )
            .where(ActivityCompletion.user_id == user_id)
        )
        if module is not None:
            stmt = stmt.where(ModuleProgress.module == module)

        if cursor_completed_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    ActivityCompletion.completed_at < cursor_completed_at,
                    and_(
                        ActivityCompletion.completed_at == cursor_completed_at,
                        ActivityCompletion.id < cursor_id,
                    ),
                )
            )

        stmt = stmt.order_by(
            ActivityCompletion.completed_at.desc(),
            ActivityCompletion.id.desc(),
        ).limit(limit + 1)

        return (await self.session.execute(stmt)).all()

    async def get_cefr_history_data(self, user_id: UUID):
        """Return `(user, completed_attempt_rows)` ordered oldest-first."""
        user = await self.session.scalar(select(User).where(User.id == user_id))
        if user is None:
            return None, []

        latest_job_rubric = (
            select(AiJob.rubric_version)
            .where(
                AiJob.assessment_attempt_id == AssessmentAttempt.id,
                AiJob.status == "SUCCEEDED",
            )
            .order_by(AiJob.finished_at.desc().nulls_last(), AiJob.id.desc())
            .limit(1)
            .correlate(AssessmentAttempt)
            .scalar_subquery()
        )
        stmt = (
            select(
                AssessmentAttempt,
                latest_job_rubric.label("job_rubric_version"),
            )
            .where(
                AssessmentAttempt.user_id == user_id,
                AssessmentAttempt.status == "COMPLETED",
            )
            .order_by(
                AssessmentAttempt.completed_at.asc().nulls_last(),
                AssessmentAttempt.started_at.asc(),
                AssessmentAttempt.id.asc(),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return user, rows






