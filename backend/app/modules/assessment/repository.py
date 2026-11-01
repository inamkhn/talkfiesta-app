"""Owner-scoped assessment persistence; callers own transactions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assessment.models import AssessmentAttempt, AssessmentStartRequest
from app.modules.auth.models import User
from app.modules.content.models import ContentItem

ACTIVE_STATUSES = ("IN_PROGRESS", "SUBMITTED", "PROCESSING", "FAILED_RETRYABLE")


class AssessmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_user(self, user_id: UUID) -> User | None:
        return await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def prior_request(
        self, user_id: UUID, key_hash: str
    ) -> AssessmentStartRequest | None:
        return await self.session.get(AssessmentStartRequest, (user_id, key_hash))

    async def attempt(
        self, user_id: UUID, attempt_id: UUID
    ) -> AssessmentAttempt | None:
        return await self.session.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.id == attempt_id, AssessmentAttempt.user_id == user_id
            )
        )

    async def active(self, user_id: UUID) -> AssessmentAttempt | None:
        return await self.session.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.user_id == user_id,
                AssessmentAttempt.kind == "INITIAL",
                AssessmentAttempt.status.in_(ACTIVE_STATUSES),
            )
        )

    async def completed(self, user_id: UUID) -> AssessmentAttempt | None:
        return await self.session.scalar(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.user_id == user_id,
                AssessmentAttempt.kind == "INITIAL",
                AssessmentAttempt.status == "COMPLETED",
            )
            .order_by(AssessmentAttempt.started_at.desc())
            .limit(1)
        )

    async def count_since(self, user_id: UUID, since: datetime) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(AssessmentAttempt)
                .where(
                    AssessmentAttempt.user_id == user_id,
                    AssessmentAttempt.kind == "INITIAL",
                    AssessmentAttempt.started_at >= since,
                )
            )
            or 0
        )

    async def bank(self, release: str) -> list[ContentItem]:
        return list(
            await self.session.scalars(
                select(ContentItem)
                .where(
                    ContentItem.kind == "ASSESSMENT_QUESTION",
                    ContentItem.status == "PUBLISHED",
                    ContentItem.release_key == release,
                )
                .order_by(ContentItem.id)
                .with_for_update(read=True)
            )
        )

    def add_attempt(self, attempt: AssessmentAttempt) -> None:
        self.session.add(attempt)

    def remember(
        self, user_id: UUID, key_hash: str, payload_hash: str, attempt_id: UUID
    ) -> None:
        self.session.add(
            AssessmentStartRequest(
                user_id=user_id,
                key_hash=key_hash,
                payload_hash=payload_hash,
                assessment_attempt_id=attempt_id,
            )
        )
