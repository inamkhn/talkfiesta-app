"""Authenticated daily speaking endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.infrastructure.cache.redis import enforce_rate_limit
from app.modules.speaking.drafts import SpeakingDraftService
from app.modules.speaking.history import SpeakingHistoryService
from app.modules.speaking.results import SpeakingResultService
from app.modules.speaking.schemas import (
    CreateSpeakingDraftRequest,
    SpeakingDraftResponse,
    SpeakingEvaluationStatus,
    SpeakingHistoryResponse,
    SpeakingSubmissionDetail,
    SpeakingTodayResponse,
    SubmitSpeakingRequest,
    SubmitSpeakingResponse,
)
from app.modules.speaking.service import SpeakingQueryService
from app.modules.speaking.submission import SpeakingSubmissionService

router = APIRouter(prefix="/speaking", tags=["Speaking"])


@router.get("/submissions", response_model=SpeakingHistoryResponse)
async def speaking_history(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
    evaluation_status: SpeakingEvaluationStatus | None = None,
) -> SpeakingHistoryResponse:
    """Read short summaries in descending submission order using a signed cursor."""
    result = await SpeakingHistoryService(db).get(
        user.id, limit, evaluation_status, cursor
    )
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get("/submissions/{submission_id}", response_model=SpeakingSubmissionDetail)
async def speaking_submission(
    submission_id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> SpeakingSubmissionDetail:
    """Poll safe evaluation progress or read saved transcript and coaching."""
    result = await SpeakingResultService(db).get(user.id, submission_id)
    response.headers["Cache-Control"] = "private, no-store"
    if result.evaluation.retry_after_seconds is not None:
        response.headers["Retry-After"] = str(result.evaluation.retry_after_seconds)
    return result


@router.post(
    "/submissions/{submission_id}/submit",
    status_code=202,
    response_model=SubmitSpeakingResponse,
)
async def submit_speaking(
    submission_id: UUID,
    payload: SubmitSpeakingRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> SubmitSpeakingResponse:
    await enforce_rate_limit(
        f"ratelimit:speaking-submit:user:{user.id}", limit=60, window_seconds=3600
    )
    result = await SpeakingSubmissionService(db).submit(
        user.id, submission_id, payload.media_upload_id, idempotency_key
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Location"] = result.submission_url
    return result


@router.get("/today", response_model=SpeakingTodayResponse)
async def speaking_today(
    user: CurrentUser, db: DbSession, response: Response
) -> SpeakingTodayResponse:
    """Read the pinned current lesson and any existing owned recording draft."""
    response.headers["Cache-Control"] = "private, no-store"
    return await SpeakingQueryService(db).get_today(user.id)


@router.post(
    "/submissions",
    status_code=201,
    response_model=SpeakingDraftResponse,
    responses={
        200: {
            "description": "Existing active draft reused",
            "model": SpeakingDraftResponse,
        }
    },
)
async def create_speaking_draft(
    payload: CreateSpeakingDraftRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> SpeakingDraftResponse:
    """Create or reuse an owned draft without crediting progress or starting AI."""
    await enforce_rate_limit(
        f"ratelimit:speaking-draft:user:{user.id}", limit=60, window_seconds=3600
    )
    result, created = await SpeakingDraftService(db).create(
        user.id, payload.content_item_id, idempotency_key
    )
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "private, no-store"
    return result
