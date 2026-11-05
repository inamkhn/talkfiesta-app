"""Signed keyset pagination of owner-scoped speaking summaries."""

import base64
import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError, ValidationAppError
from app.modules.content.models import ContentItem
from app.modules.learning.models import ActivityCompletion
from app.modules.practice.models import PracticeSubmission
from app.modules.speaking.schemas import (
    SpeakingEvaluationStatus,
    SpeakingHistoryItem,
    SpeakingHistoryResponse,
)

logger = logging.getLogger(__name__)
CURSOR_CONTEXT = b"talkfiesta:speaking-history:v1:"


class HistoryCursor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    user_id: UUID
    evaluation_status: SpeakingEvaluationStatus | None
    submitted_at: AwareDatetime | None
    submission_id: UUID
    expires_at: AwareDatetime


def encode_cursor(cursor: HistoryCursor) -> str:
    payload = base64.urlsafe_b64encode(cursor.model_dump_json().encode()).rstrip(b"=")
    signature = hmac.new(
        settings.jwt_secret_key.encode(), CURSOR_CONTEXT + payload, hashlib.sha256
    ).hexdigest()
    return payload.decode() + "." + signature


def decode_cursor(
    value: str, user_id: UUID, evaluation_status: str | None
) -> HistoryCursor:
    try:
        if not 1 <= len(value) <= 2048:
            raise ValueError("Invalid size")
        payload, signature = value.split(".")
        expected = hmac.new(
            settings.jwt_secret_key.encode(),
            CURSOR_CONTEXT + payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid signature")
        data = base64.b64decode(
            payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True
        )
        cursor = HistoryCursor.model_validate_json(data)
        if (
            cursor.user_id != user_id
            or cursor.evaluation_status != evaluation_status
            or cursor.expires_at <= datetime.now(UTC)
        ):
            raise ValueError("Invalid scope or expiration")
        return cursor
    except (ValueError, TypeError, ValidationError):
        raise ValidationAppError(
            "Invalid or expired history cursor. Restart pagination.",
            code="INVALID_CURSOR",
        ) from None


def history_statement(
    user_id: UUID,
    limit: int,
    evaluation_status: str | None,
    cursor: HistoryCursor | None,
):
    credited = (
        select(ActivityCompletion.id)
        .where(
            ActivityCompletion.user_id == user_id,
            ActivityCompletion.source_submission_id == PracticeSubmission.id,
            ActivityCompletion.module_progress_id
            == PracticeSubmission.module_progress_id,
            ActivityCompletion.content_item_id == PracticeSubmission.content_item_id,
        )
        .correlate(PracticeSubmission)
        .exists()
    )
    statement = (
        select(
            PracticeSubmission.id,
            PracticeSubmission.content_item_id,
            ContentItem.title,
            PracticeSubmission.submitted_at,
            PracticeSubmission.status,
            PracticeSubmission.evaluation_status,
            PracticeSubmission.feedback["reviewable"].label("reviewable"),
            PracticeSubmission.feedback["scores"]["grammar"].label("grammar_score"),
            credited.label("credited"),
        )
        .join(ContentItem, ContentItem.id == PracticeSubmission.content_item_id)
        .where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.mode == "RECORDED_SPEAKING",
        )
    )
    if evaluation_status is not None:
        statement = statement.where(
            PracticeSubmission.evaluation_status == evaluation_status
        )
    if cursor is not None:
        if cursor.submitted_at is None:
            boundary = and_(
                PracticeSubmission.submitted_at.is_(None),
                PracticeSubmission.id < cursor.submission_id,
            )
        else:
            boundary = or_(
                PracticeSubmission.submitted_at < cursor.submitted_at,
                and_(
                    PracticeSubmission.submitted_at == cursor.submitted_at,
                    PracticeSubmission.id < cursor.submission_id,
                ),
                PracticeSubmission.submitted_at.is_(None),
            )
        statement = statement.where(boundary)
    return statement.order_by(
        PracticeSubmission.submitted_at.desc().nulls_last(),
        PracticeSubmission.id.desc(),
    ).limit(limit + 1)


class SpeakingHistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(
        self,
        user_id: UUID,
        limit: int,
        evaluation_status: str | None,
        cursor: str | None,
    ) -> SpeakingHistoryResponse:
        boundary = (
            decode_cursor(cursor, user_id, evaluation_status)
            if cursor is not None
            else None
        )
        rows = (
            await self.session.execute(
                history_statement(user_id, limit, evaluation_status, boundary)
            )
        ).all()
        items = []
        try:
            for row in rows[:limit]:
                if row.status == "ACCEPTED":
                    if (
                        not row.credited
                        or row.submitted_at is None
                        or row.evaluation_status == "NOT_REQUIRED"
                    ):
                        raise ValueError("Accepted submission is inconsistent")
                    activity_status = "COMPLETED"
                elif row.status in ("DRAFT", "REJECTED"):
                    if row.credited or row.evaluation_status != "NOT_REQUIRED":
                        raise ValueError("Unaccepted submission is inconsistent")
                    activity_status = (
                        "IN_PROGRESS" if row.status == "DRAFT" else "REJECTED"
                    )
                else:
                    raise ValueError("Unknown submission lifecycle state")
                score = None
                if row.evaluation_status == "COMPLETED":
                    if type(row.reviewable) is not bool:
                        raise ValueError("Missing reviewability")
                    if row.reviewable:
                        if type(row.grammar_score) is not int:
                            raise ValueError("Missing grammar score")
                        score = row.grammar_score
                    elif row.grammar_score is not None:
                        raise ValueError("Unscorable speech has a score")
                items.append(
                    SpeakingHistoryItem(
                        submission_id=row.id,
                        content_item_id=row.content_item_id,
                        title=row.title,
                        submitted_at=row.submitted_at,
                        activity_status=activity_status,
                        evaluation_status=row.evaluation_status,
                        grammar_score=score,
                    )
                )
            next_cursor = None
            if len(rows) > limit:
                last = rows[limit - 1]
                next_cursor = encode_cursor(
                    HistoryCursor(
                        user_id=user_id,
                        evaluation_status=evaluation_status,
                        submitted_at=last.submitted_at,
                        submission_id=last.id,
                        expires_at=datetime.now(UTC) + timedelta(hours=24),
                    )
                )
            return SpeakingHistoryResponse(items=items, next_cursor=next_cursor)
        except (ValueError, ValidationError):
            logger.error("speaking_history_inconsistent user_id=%s", user_id)
            raise ServiceUnavailableError(
                "Speaking history is temporarily unavailable.",
                code="SPEAKING_HISTORY_UNAVAILABLE",
            ) from None
