"""Start or resume an initial assessment in a single serialized transaction."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
)
from app.modules.assessment.blueprint import validate_bank
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.assessment.repository import AssessmentRepository
from app.modules.assessment.schemas import (
    AssessmentDetailResponse,
    StartAssessmentRequest,
    StartAssessmentResponse,
)
from app.modules.assessment.selection import SEQUENCE
from app.modules.onboarding.schemas import SavePreferencesRequest


class AssessmentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AssessmentRepository(session)

    async def get(self, user_id: UUID, attempt_id: UUID) -> AssessmentDetailResponse:
        attempt = await self.repository.attempt(user_id, attempt_id)
        if attempt is None:
            raise NotFoundError("Assessment not found.")
        rows = list(
            await self.session.scalars(
                select(AssessmentResponse)
                .where(AssessmentResponse.assessment_attempt_id == attempt.id)
                .order_by(AssessmentResponse.position)
            )
        )
        total_items = len(SEQUENCE)
        answered_items = sum(
            1 for row in rows if row.status in ("ANSWERED", "SKIPPED")
        )
        assigned = [row.position for row in rows if row.status == "ASSIGNED"]
        current_position = assigned[0] if assigned else None
        can_submit = (
            attempt.status == "IN_PROGRESS"
            and answered_items == total_items
            and current_position is None
        )
        return AssessmentDetailResponse(
            id=attempt.id,
            kind=attempt.kind,
            status=attempt.status,
            content_release=attempt.content_release,
            total_items=total_items,
            answered_items=answered_items,
            current_position=current_position,
            can_submit=can_submit,
        )

    async def start(
        self, user_id: UUID, payload: StartAssessmentRequest, key: str
    ) -> StartAssessmentResponse:
        user = await self.repository.lock_user(user_id)
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        payload_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
        prior = await self.repository.prior_request(user_id, key_hash)
        if prior:
            if prior.payload_hash != payload_hash:
                raise ConflictError(
                    "This key was used with a different request.",
                    code="IDEMPOTENCY_KEY_REUSED",
                )
            attempt = await self.repository.attempt(
                user_id, prior.assessment_attempt_id
            )
            if attempt is None:
                raise ConflictError(
                    "The original assessment is missing.",
                    code="ASSESSMENT_STATE_INCONSISTENT",
                )
            return self.response(attempt, resumed=True)
        if user.onboarding_status == "COMPLETED":
            raise ConflictError(
                "Initial onboarding is already completed.",
                code="ONBOARDING_ALREADY_COMPLETED",
            )
        attempt = await self.repository.active(user_id)
        if attempt is not None:
            self.repository.remember(user_id, key_hash, payload_hash, attempt.id)
            await self.session.commit()
            return self.response(attempt, resumed=True)
        completed = await self.repository.completed(user_id)
        if completed is not None:
            raise ConflictError(
                "View the completed assessment result before continuing.",
                code="ASSESSMENT_ALREADY_COMPLETED",
                headers={"Location": f"/api/v1/assessments/{completed.id}/result"},
            )
        if user.onboarding_status not in ("PREFERENCES_SAVED", "ASSESSING"):
            raise ConflictError(
                "Save onboarding preferences first.", code="PREFERENCES_REQUIRED"
            )
        try:
            SavePreferencesRequest.model_validate(
                {
                    **{
                        k: v
                        for k, v in user.preferences.items()
                        if k in SavePreferencesRequest.model_fields
                    },
                    "timezone": user.timezone,
                }
            )
        except ValidationError as exc:
            raise ConflictError(
                "Save valid onboarding preferences first.", code="PREFERENCES_REQUIRED"
            ) from exc
        if (
            await self.repository.count_since(
                user_id, datetime.now(UTC) - timedelta(days=1)
            )
            >= settings.assessment_starts_per_day
        ):
            raise RateLimitedError(
                "Daily assessment start limit reached.",
                retry_after=86400,
                code="ASSESSMENT_START_LIMIT",
            )
        release = settings.assessment_content_release
        validate_bank(await self.repository.bank(release))
        attempt = AssessmentAttempt(
            id=uuid4(),
            user_id=user.id,
            kind="INITIAL",
            status="IN_PROGRESS",
            content_release=release,
        )
        self.repository.add_attempt(attempt)
        # Flush the parent before inserting the durable request-key reference.
        await self.session.flush()
        self.repository.remember(user_id, key_hash, payload_hash, attempt.id)
        user.onboarding_status = "ASSESSING"
        await self.session.commit()
        return self.response(attempt, resumed=False)

    @staticmethod
    def response(
        attempt: AssessmentAttempt, *, resumed: bool
    ) -> StartAssessmentResponse:
        return StartAssessmentResponse(
            id=attempt.id,
            status=attempt.status,
            content_release=attempt.content_release,
            resumed=resumed,
        )
