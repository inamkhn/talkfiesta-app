"""Onboarding routing and transactional preference saves."""

from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.modules.learning.models import LearningPlan, ModuleProgress
from app.modules.onboarding.curriculum import MODULES, select_curriculum
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schemas import (
    CompleteOnboardingResponse,
    LearningPreferences,
    OnboardingState,
    SavePreferencesRequest,
    SavePreferencesResponse,
)


class OnboardingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = OnboardingRepository(session)

    async def get_state(self, user_id: UUID) -> OnboardingState:
        snapshot = await self._repository.read_state(user_id)
        if snapshot is None:
            raise UnauthorizedError("The account no longer exists.")
        user, attempt = snapshot
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")
        if user.onboarding_status == "COMPLETED":
            return OnboardingState(
                status="COMPLETED", next_step="DASHBOARD", can_access_dashboard=True
            )
        if attempt is not None:
            if attempt.status == "COMPLETED":
                if attempt.result is None:
                    raise ConflictError(
                        "Assessment result is incomplete.",
                        code="ONBOARDING_STATE_INCONSISTENT",
                    )
                status, step = "RESULT_READY", "ASSESSMENT_RESULT"
            elif attempt.status == "IN_PROGRESS":
                status, step = "ASSESSING", "ASSESSMENT"
            elif attempt.status == "FAILED_FINAL":
                status, step = "ASSESSING", "ASSESSMENT_RETRY"
            else:
                # Retryable failures belong to the existing worker job; do not
                # send the browser back to editable questions or start a new job.
                status, step = "ASSESSING", "ASSESSMENT_PROCESSING"
            return OnboardingState(
                status=status,
                next_step=step,
                active_assessment_id=attempt.id,
                assessment_status=attempt.status,
            )
        if user.onboarding_status in ("ASSESSING", "RESULT_READY"):
            raise ConflictError(
                "The onboarding assessment is missing.",
                code="ONBOARDING_STATE_INCONSISTENT",
            )
        return OnboardingState(
            status=user.onboarding_status,
            next_step="PREFERENCES"
            if user.onboarding_status == "NOT_STARTED"
            else "ASSESSMENT",
        )

    async def save_preferences(
        self, user_id: UUID, payload: SavePreferencesRequest
    ) -> SavePreferencesResponse:
        user = await self._repository.lock_user(user_id)
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")
        # PUT replaces the full learning-preference subset, preserving unrelated
        # account preferences such as reminder settings. New dict tracks JSONB.
        preferences = payload.model_dump(mode="json", exclude={"timezone"})
        merged = {**user.preferences, **preferences}
        if user.preferences != merged:
            user.preferences = merged
        if user.timezone != payload.timezone:
            user.timezone = payload.timezone
        if user.onboarding_status == "NOT_STARTED":
            user.onboarding_status = "PREFERENCES_SAVED"
        await self._session.commit()
        return SavePreferencesResponse(status=user.onboarding_status)

    async def complete(
        self, user_id: UUID, attempt_id: UUID
    ) -> CompleteOnboardingResponse:
        user = await self._repository.lock_user(user_id)
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")
        attempt = await self._repository.get_assessment(user_id, attempt_id)
        if attempt is None:
            raise NotFoundError("Assessment not found.")
        existing = await self._repository.get_first_plan(user_id)
        if existing is not None:
            if existing.source_assessment_id != attempt_id:
                raise ConflictError(
                    "Onboarding already used a different assessment.",
                    code="ONBOARDING_ALREADY_COMPLETED",
                )
            modules = await self._repository.get_modules(existing.id)
            if (
                user.onboarding_status != "COMPLETED"
                or len(modules) != 3
                or {row.module for row in modules} != set(MODULES)
            ):
                raise ConflictError(
                    "The saved learning plan is incomplete.",
                    code="ONBOARDING_STATE_INCONSISTENT",
                )
            # Return the original plan even after it is paused/completed; never
            # recreate or reset progress on a delayed retry.
            return CompleteOnboardingResponse(learning_plan_id=existing.id)
        if user.onboarding_status == "COMPLETED":
            raise ConflictError(
                "The onboarding plan is missing.", code="ONBOARDING_STATE_INCONSISTENT"
            )
        if (
            attempt.kind != "INITIAL"
            or attempt.status != "COMPLETED"
            or not attempt.result
        ):
            raise ConflictError(
                "A completed initial assessment is required.",
                code="ASSESSMENT_NOT_READY",
            )
        if attempt.placement_cefr not in ("A1", "A2", "B1", "B2", "C1", "C2"):
            raise ConflictError(
                "The assessment has no usable CEFR placement.",
                code="PLACEMENT_UNAVAILABLE",
            )
        try:
            preferences = LearningPreferences.model_validate(
                {
                    key: value
                    for key, value in user.preferences.items()
                    if key in LearningPreferences.model_fields
                }
            )
        except ValidationError as exc:
            raise ConflictError(
                "Save complete learning preferences first.", code="PREFERENCES_REQUIRED"
            ) from exc
        curriculum = await select_curriculum(
            self._repository, attempt.placement_cefr, preferences.goals
        )
        plan_id = uuid4()
        plan = LearningPlan(
            id=plan_id,
            user_id=user.id,
            source_assessment_id=attempt.id,
            cycle=1,
            status="ACTIVE",
            placement_cefr=attempt.placement_cefr,
            plan_config={
                **preferences.model_dump(mode="json"),
                "modules": list(MODULES),
                "timezone": user.timezone,
            },
        )
        modules = [
            ModuleProgress(
                learning_plan_id=plan_id,
                module=module,
                content_release=curriculum[module][0],
                goal_variant=curriculum[module][1],
                cefr_level=attempt.placement_cefr,
                current_day=1,
                status="ACTIVE",
                prioritized=module in preferences.focus_areas,
            )
            for module in MODULES
        ]
        self._repository.add_plan(plan, modules)
        user.onboarding_status = "COMPLETED"
        user.current_cefr = attempt.placement_cefr
        await self._session.commit()
        return CompleteOnboardingResponse(learning_plan_id=plan_id)
