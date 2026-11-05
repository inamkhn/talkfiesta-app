"""Owner-scoped, read-only learning-plan query service."""

import logging
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.modules.learning.repository import LearningPlanRepository
from app.modules.learning.schemas import (
    CurrentPlanResponse,
    ModuleSummary,
    ModuleTimelineResponse,
    PlanSummary,
    TimelineDay,
    TodayActivity,
    TodayPlanResponse,
)

logger = logging.getLogger(__name__)
MODULE_ORDER = ("SPEAKING", "VOCABULARY", "WRITING")


class LearningPlanQueryService:
    def __init__(self, session: AsyncSession):
        self.repository = LearningPlanRepository(session)

    async def get_current(self, user_id: UUID) -> CurrentPlanResponse:
        rows = await self.repository.current(user_id)
        return self.current_response(user_id, rows)

    async def get_timeline(self, user_id: UUID, module: str) -> ModuleTimelineResponse:
        rows = await self.repository.timeline(user_id, module)
        # The content join expands each enrollment into lesson rows. Validate the
        # same plan snapshot once per enrollment, without a second database read.
        enrollments = {
            row.ModuleProgress.id if row.ModuleProgress is not None else None: row
            for row in rows
        }
        current = self.current_response(user_id, list(enrollments.values()))
        progress = next(
            (item for item in current.modules if item.module == module), None
        )
        if progress is None:
            raise NotFoundError(
                "This module is not enrolled in the active plan.",
                code="MODULE_NOT_ENROLLED",
            )
        published = {}
        credits = {}
        for row in rows:
            if row.ModuleProgress.id != progress.progress_id or row.content_day is None:
                continue
            if row.content_status == "PUBLISHED":
                published[row.content_day] = row.title
            if row.credited_at is not None:
                previous = credits.get(row.content_day)
                if previous is None or row.credited_at < previous.credited_at:
                    credits[row.content_day] = row
        if (
            progress.status == "ACTIVE"
            and progress.current_day not in credits
            and progress.current_day not in published
        ):
            raise ConflictError(
                "The required curriculum content is not available.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )
        try:
            days = []
            for day in range(1, 22):
                credit = credits.get(day)
                days.append(
                    TimelineDay(
                        day=day,
                        state="COMPLETED"
                        if credit is not None
                        else (
                            "AVAILABLE"
                            if progress.status == "ACTIVE"
                            and day == progress.current_day
                            and day in published
                            else "LOCKED"
                        ),
                        completed_at=credit.credited_at if credit is not None else None,
                        title=credit.title
                        if credit is not None
                        else published.get(day),
                    )
                )
            return ModuleTimelineResponse(
                module=progress.module,
                progress_id=progress.progress_id,
                cycle=current.plan.cycle,
                current_day=progress.current_day,
                status=progress.status,
                completed_days=len(credits),
                days=days,
            )
        except ValidationError:
            logger.error(
                "timeline_inconsistent user_id=%s progress_id=%s",
                user_id,
                progress.progress_id,
            )
            raise ServiceUnavailableError(
                "The saved timeline is incomplete. Please try again later.",
                code="LEARNING_PLAN_UNAVAILABLE",
            ) from None

    async def get_today(self, user_id: UUID) -> TodayPlanResponse:
        rows = await self.repository.today(user_id)
        return self.today_response(user_id, rows)

    def today_response(self, user_id: UUID, rows) -> TodayPlanResponse:
        """Project an already-loaded snapshot for today's endpoint or dashboard."""
        current = self.current_response(user_id, rows)
        by_progress = {row.ModuleProgress.id: row for row in rows}
        activities = []
        try:
            for module in current.modules:
                row = by_progress[module.progress_id]
                if module.status == "COMPLETED":
                    activities.append(
                        TodayActivity(
                            module=module.module, day=21, activity_status="COMPLETED"
                        )
                    )
                    continue
                if module.status != "ACTIVE" or row.content_item_id is None:
                    raise ConflictError(
                        "The required curriculum content is not available.",
                        code="CURRICULUM_CONTENT_UNAVAILABLE",
                    )
                activities.append(
                    TodayActivity(
                        module=module.module,
                        day=module.current_day,
                        content_item_id=row.content_item_id,
                        title=row.title,
                        description=row.description,
                        content_kind=row.content_kind,
                        estimated_minutes=row.estimated_minutes,
                        activity_status="IN_PROGRESS"
                        if row.has_draft
                        else "NOT_STARTED",
                        route=f"/{module.module.lower()}/day/{module.current_day}",
                    )
                )
            return TodayPlanResponse(
                plan_id=current.plan.id,
                cycle=current.plan.cycle,
                daily_target_minutes=current.plan.daily_target_minutes,
                timezone=rows[0].timezone,
                activities=activities,
            )
        except ValidationError:
            logger.error(
                "today_plan_inconsistent user_id=%s plan_id=%s",
                user_id,
                current.plan.id,
            )
            raise ServiceUnavailableError(
                "The saved learning activities are incomplete. Please try again later.",
                code="LEARNING_PLAN_UNAVAILABLE",
            ) from None

    def current_response(self, user_id: UUID, rows) -> CurrentPlanResponse:
        if not rows:
            raise NotFoundError("Account not found.")
        if rows[0].onboarding_status != "COMPLETED":
            raise ConflictError(
                "Complete onboarding to start learning.", code="ONBOARDING_REQUIRED"
            )
        plan = rows[0].LearningPlan
        if plan is None:
            logger.warning("active_plan_missing user_id=%s", user_id)
            raise NotFoundError(
                "No active learning plan was found.", code="ACTIVE_PLAN_NOT_FOUND"
            )
        try:
            if len({row.LearningPlan.id for row in rows}) != 1 or not isinstance(
                plan.plan_config, dict
            ):
                raise ValueError("Invalid active plan state")
            config = plan.plan_config
            modules = [
                ModuleSummary(
                    module=progress.module,
                    progress_id=progress.id,
                    status=progress.status,
                    current_day=progress.current_day,
                    completed_days=row.completed_days,
                    target_cefr=progress.cefr_level,
                    prioritized=progress.prioritized,
                )
                for row in rows
                if (progress := row.ModuleProgress) is not None
            ]
            if len({module.module for module in modules}) != len(modules):
                raise ValueError("Duplicate enrollment")
            modules.sort(key=lambda module: MODULE_ORDER.index(module.module))
            return CurrentPlanResponse(
                plan=PlanSummary(
                    id=plan.id,
                    cycle=plan.cycle,
                    status=plan.status,
                    placement_cefr=plan.placement_cefr,
                    goals=config.get("goals"),
                    focus_areas=config.get("focus_areas"),
                    daily_target_minutes=config.get("daily_minutes"),
                    created_at=plan.created_at,
                ),
                modules=modules,
            )
        except (ValidationError, ValueError):
            logger.error(
                "learning_plan_inconsistent user_id=%s plan_id=%s", user_id, plan.id
            )
            raise ServiceUnavailableError(
                "The saved learning plan is incomplete. Please try again later.",
                code="LEARNING_PLAN_UNAVAILABLE",
            ) from None
