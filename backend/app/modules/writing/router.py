"""Authenticated daily writing endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Header, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.infrastructure.cache.redis import enforce_rate_limit
from app.modules.writing.schemas import (
    CreateWritingRevisionRequest,
    CreateWritingSubmissionRequest,
    SaveWritingDraftRequest,
    SaveWritingDraftResponse,
    SubmitWritingSubmissionRequest,
    SubmitWritingSubmissionResponse,
    WritingDraftResponse,
    WritingPortfolioResponse,
    WritingPortfolioSort,
    WritingRevisionsResponse,
    WritingSubmissionDetailResponse,
    WritingTodayResponse,
)
from app.modules.writing.service import WritingQueryService
from app.modules.writing.submissions import WritingSubmissionService

router = APIRouter(prefix="/writing", tags=["Writing"])


@router.get("/today", response_model=WritingTodayResponse)
async def writing_today(
    user: CurrentUser, db: DbSession, response: Response
) -> WritingTodayResponse:
    """Read the pinned current writing prompt, completion state, and active draft ID."""
    response.headers["Cache-Control"] = "private, no-store"
    return await WritingQueryService(db).get_today(user.id)


@router.post(
    "/submissions",
    status_code=201,
    response_model=WritingDraftResponse,
    responses={
        200: {
            "description": "Existing active writing draft reused",
            "model": WritingDraftResponse,
        }
    },
)
async def create_writing_submission(
    payload: CreateWritingSubmissionRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> WritingDraftResponse:
    """Start or resume the original writing draft (revision_number=1) for today's prompt."""
    await enforce_rate_limit(
        f"ratelimit:writing-draft-create:user:{user.id}",
        limit=60,
        window_seconds=3600,
    )
    result, created = await WritingSubmissionService(db).create_or_resume(
        user.id, payload.content_item_id, idempotency_key
    )
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.patch(
    "/submissions/{submission_id}",
    response_model=SaveWritingDraftResponse,
)
async def save_writing_submission_draft(
    submission_id: UUID,
    payload: SaveWritingDraftRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> SaveWritingDraftResponse:
    """Autosave plain-text writing draft with edit_version optimistic concurrency."""
    response.headers["Cache-Control"] = "private, no-store"
    return await WritingSubmissionService(db).save_draft(
        user.id, submission_id, payload
    )


@router.post(
    "/submissions/{submission_id}/submit",
    status_code=202,
    response_model=SubmitWritingSubmissionResponse,
)
async def submit_writing_submission(
    submission_id: UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
    payload: Annotated[SubmitWritingSubmissionRequest | None, Body()] = None,
) -> SubmitWritingSubmissionResponse:
    """Validate word count, freeze draft, credit daily activity once, and queue AI evaluation."""
    await enforce_rate_limit(
        f"ratelimit:writing-submit:user:{user.id}",
        limit=60,
        window_seconds=3600,
    )
    result = await WritingSubmissionService(db).submit(
        user.id, submission_id, idempotency_key, payload
    )
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get(
    "/submissions/{submission_id}",
    response_model=WritingSubmissionDetailResponse,
)
async def get_writing_submission(
    submission_id: UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> WritingSubmissionDetailResponse:
    """Read an owned writing submission (draft, processing status, or completed rubric report)."""
    response.headers["Cache-Control"] = "private, no-store"
    return await WritingSubmissionService(db).get_submission(user.id, submission_id)


@router.post(
    "/submissions/{submission_id}/revisions",
    status_code=201,
    response_model=WritingDraftResponse,
    responses={
        200: {
            "description": "Existing active revision draft reused",
            "model": WritingDraftResponse,
        }
    },
)
async def create_writing_revision(
    submission_id: UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
    payload: Annotated[CreateWritingRevisionRequest | None, Body()] = None,
) -> WritingDraftResponse:
    """Start or resume a revision draft (revision_number 2..4) after base evaluation completes."""
    await enforce_rate_limit(
        f"ratelimit:writing-revision-create:user:{user.id}",
        limit=60,
        window_seconds=3600,
    )
    result, created = await WritingSubmissionService(db).create_revision(
        user.id, submission_id, idempotency_key, payload
    )
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get(
    "/submissions/{submission_id}/revisions",
    response_model=WritingRevisionsResponse,
)
async def get_writing_revisions(
    submission_id: UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> WritingRevisionsResponse:
    """Return all versions (1..4) in the submission's revision group and latest comparison."""
    response.headers["Cache-Control"] = "private, no-store"
    return await WritingSubmissionService(db).get_revisions(user.id, submission_id)


@router.get("/portfolio", response_model=WritingPortfolioResponse)
async def writing_portfolio(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
    sort: Annotated[WritingPortfolioSort, Query()] = "recent",
) -> WritingPortfolioResponse:
    """Return cursor-paginated writing history showing one card per revision_group_id."""
    response.headers["Cache-Control"] = "private, no-store"
    return await WritingSubmissionService(db).get_portfolio(
        user.id,
        limit=limit,
        cursor=cursor,
        sort=sort,
    )








