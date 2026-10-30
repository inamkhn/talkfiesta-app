"""Authenticated self-service user profile routes."""

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.modules.users.schemas import UpdateProfileRequest, UserProfile
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfile, summary="Get the current user's profile")
async def get_me(user: CurrentUser, response: Response) -> UserProfile:
    response.headers["Cache-Control"] = "no-store"
    return UserProfile.model_validate(user)


@router.patch(
    "/me",
    response_model=UserProfile,
    summary="Update your display name, profile, and preferences",
)
async def update_me(
    payload: UpdateProfileRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> UserProfile:
    response.headers["Cache-Control"] = "no-store"
    return await UserService(db).update_profile(user, payload)
