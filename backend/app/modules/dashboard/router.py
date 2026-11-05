"""Authenticated learner dashboard."""

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.modules.dashboard.query_service import DashboardQueryService
from app.modules.dashboard.schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
async def dashboard(
    user: CurrentUser, db: DbSession, response: Response
) -> DashboardResponse:
    """Read progress, today's lessons, streaks and pending feedback."""
    response.headers["Cache-Control"] = "private, no-store"
    return await DashboardQueryService(db).get_overview(user.id)
