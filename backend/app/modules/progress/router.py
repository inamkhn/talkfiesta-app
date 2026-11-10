"""HTTP router for `/api/v1/progress` endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.modules.progress.schemas import (
    AchievementFilterStatus,
    AchievementsResponse,
    ActivityCalendarResponse,
    ActivityHistoryResponse,
    CefrHistoryResponse,
    ModuleDetailResponse,
    ModuleLiteral,
    ModuleTrendResponse,
    OverviewScope,
    ProgressOverviewResponse,
    ProgressStreaksResponse,
    TrendGranularity,
)
from app.modules.progress.service import ProgressQueryService
from app.modules.progress.trends import TrendQueryService

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("/overview", response_model=ProgressOverviewResponse)
async def get_progress_overview(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    scope: Annotated[OverviewScope, Query()] = "current",
) -> ProgressOverviewResponse:
    """Return cross-module progress, practice totals, streak summary, and vocabulary mastery."""
    response.headers["Cache-Control"] = "private, no-store"
    return await ProgressQueryService(db).get_overview(user.id, scope=scope)


@router.get("/modules/{module}", response_model=ModuleDetailResponse)
async def get_module_progress_detail(
    module: ModuleLiteral,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    cycle: Annotated[int | None, Query(ge=1, le=5)] = None,
) -> ModuleDetailResponse:
    """Return module-specific 21-day progress, skill metrics, and recent submissions."""
    response.headers["Cache-Control"] = "private, no-store"
    return await ProgressQueryService(db).get_module(
        user.id, module=module, cycle=cycle
    )


@router.get("/streaks", response_model=ProgressStreaksResponse)
async def get_progress_streaks(
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> ProgressStreaksResponse:
    """Return deterministic streak summary from distinct credited local practice dates."""
    response.headers["Cache-Control"] = "private, no-store"
    return await ProgressQueryService(db).get_streaks(user.id)


@router.get("/activity-calendar", response_model=ActivityCalendarResponse)
async def get_activity_calendar(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    module: Annotated[ModuleLiteral | None, Query()] = None,
) -> ActivityCalendarResponse:
    """Return sparse date-bucketed completion heatmap for up to 366 days."""
    response.headers["Cache-Control"] = "private, no-store"
    return await ProgressQueryService(db).get_activity_calendar(
        user.id, date_from=date_from, date_to=date_to, module=module
    )


@router.get("/achievements", response_model=AchievementsResponse)
async def get_progress_achievements(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    status: Annotated[AchievementFilterStatus, Query()] = "all",
) -> AchievementsResponse:
    """Return earned and locked achievement badges with progress counters."""
    response.headers["Cache-Control"] = "private, no-store"
    return await ProgressQueryService(db).get_achievements(user.id, status=status)


@router.get("/modules/{module}/trends", response_model=ModuleTrendResponse)
async def get_module_trends(
    module: ModuleLiteral,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    metric: Annotated[str, Query(min_length=1, max_length=64)],
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Annotated[TrendGranularity, Query()] = "week",
    rubric_version: Annotated[
        str | None, Query(min_length=1, max_length=64)
    ] = None,
) -> ModuleTrendResponse:
    """Return date-bucketed performance trend points for a module and metric."""
    response.headers["Cache-Control"] = "private, no-store"
    return await TrendQueryService(db).get_trend(
        user.id,
        module=module,
        metric=metric,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
        rubric_version=rubric_version,
    )


@router.get("/activity-history", response_model=ActivityHistoryResponse)
async def get_activity_history(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    module: Annotated[ModuleLiteral | None, Query()] = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ActivityHistoryResponse:
    """Return cursor-paginated chronological ledger of credited activities."""
    response.headers["Cache-Control"] = "private, no-store"
    return await ProgressQueryService(db).get_activity_history(
        user.id, module=module, cursor=cursor, limit=limit
    )


@router.get("/cefr-history", response_model=CefrHistoryResponse)
async def get_cefr_history(
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> CefrHistoryResponse:
    """Return chronological provisional CEFR placement and reassessment history."""
    response.headers["Cache-Control"] = "private, no-store"
    return await ProgressQueryService(db).get_cefr_history(user.id)







