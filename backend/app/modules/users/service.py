"""Profile updates for the account resolved by the authentication dependency."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.users.schemas import UpdateProfileRequest, UserProfile


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def update_profile(
        self, user: User, payload: UpdateProfileRequest
    ) -> UserProfile:
        if payload.model_fields_set:
            # Reload under a lock: concurrent patches must merge with the latest
            # saved JSON, not the snapshot loaded during authentication.
            user = (
                await self._session.execute(
                    select(User)
                    .where(User.id == user.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one()
            if "display_name" in payload.model_fields_set:
                user.display_name = payload.display_name
            if "profile" in payload.model_fields_set:
                user.profile = {**user.profile, **payload.profile}
            if "preferences" in payload.model_fields_set:
                user.preferences = {**user.preferences, **payload.preferences}
            await self._session.commit()
            await self._session.refresh(user)
        return UserProfile.model_validate(user)
