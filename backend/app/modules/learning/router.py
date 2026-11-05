"""Authenticated learning-plan reads."""

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.modules.learning.schemas import (
    CurrentPlanResponse,
    ModuleTimelineResponse,
    TimelineModule,
    TodayPlanResponse,
)
from app.modules.learning.service import LearningPlanQueryService

router = APIRouter(prefix="/learning-plans", tags=["Learning plans"])


@router.get("/current", response_model=CurrentPlanResponse)
async def current_plan(
    user: CurrentUser, db: DbSession, response: Response
) -> CurrentPlanResponse:
    """Read the active plan, enrolled modules, and credited required days."""
    response.headers["Cache-Control"] = "private, no-store"
    return await LearningPlanQueryService(db).get_current(user.id)


@router.get("/current/today", response_model=TodayPlanResponse)
async def today_plan(
    user: CurrentUser, db: DbSession, response: Response
) -> TodayPlanResponse:
    """Read the next required activity in each enrolled module."""
    response.headers["Cache-Control"] = "private, no-store"
    return await LearningPlanQueryService(db).get_today(user.id)


@router.get("/current/modules/{module}/timeline", response_model=ModuleTimelineResponse)
async def module_timeline(
    module: TimelineModule, user: CurrentUser, db: DbSession, response: Response
) -> ModuleTimelineResponse:
    """Read all 21 curriculum days and their credited completion state."""
    response.headers["Cache-Control"] = "private, no-store"
    return await LearningPlanQueryService(db).get_timeline(user.id, module)
