"""Authenticated onboarding state and preference endpoints."""

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.modules.onboarding.schemas import (
    CompleteOnboardingRequest,
    CompleteOnboardingResponse,
    OnboardingState,
    SavePreferencesRequest,
    SavePreferencesResponse,
)
from app.modules.onboarding.service import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.post(
    "/complete",
    response_model=CompleteOnboardingResponse,
    summary="Accept placement and initialize your learning plan",
)
async def complete_onboarding(
    payload: CompleteOnboardingRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> CompleteOnboardingResponse:
    response.headers["Cache-Control"] = "no-store"
    return await OnboardingService(db).complete(user.id, payload.assessment_attempt_id)


@router.get(
    "/state",
    response_model=OnboardingState,
    summary="Resume onboarding from saved progress",
)
async def get_state(
    user: CurrentUser, db: DbSession, response: Response
) -> OnboardingState:
    response.headers["Cache-Control"] = "no-store"
    return await OnboardingService(db).get_state(user.id)


@router.put(
    "/preferences",
    response_model=SavePreferencesResponse,
    summary="Save validated learning preferences",
)
async def save_preferences(
    payload: SavePreferencesRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> SavePreferencesResponse:
    response.headers["Cache-Control"] = "no-store"
    return await OnboardingService(db).save_preferences(user.id, payload)
