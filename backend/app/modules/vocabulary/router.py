"""Authenticated daily vocabulary endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Header, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.infrastructure.cache.redis import enforce_rate_limit
from app.modules.vocabulary.practice import VocabPracticeService
from app.modules.vocabulary.schemas import (
    CreateVocabPracticeRequest,
    DueReviewsResponse,
    SaveVocabPracticeAnswersRequest,
    SaveVocabPracticeAnswersResponse,
    SubmitVocabPracticeRequest,
    SubmitVocabPracticeResponse,
    SubmitVocabReviewRequest,
    SubmitVocabReviewResponse,
    VocabPracticeSessionResponse,
    VocabularyBankResponse,
    VocabularyBankStatus,
    VocabularyProgressResponse,
    VocabularyTodayResponse,
    VocabularyWordDetailResponse,
)
from app.modules.vocabulary.service import VocabularyQueryService

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary"])


@router.get("/today", response_model=VocabularyTodayResponse)
async def vocabulary_today(
    user: CurrentUser, db: DbSession, response: Response
) -> VocabularyTodayResponse:
    """Read the pinned current 10-word lesson, active quiz draft, and due review count."""
    response.headers["Cache-Control"] = "private, no-store"
    return await VocabularyQueryService(db).get_today(user.id)


@router.get("/words/{word_id}", response_model=VocabularyWordDetailResponse)
async def vocabulary_word(
    word_id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> VocabularyWordDetailResponse:
    """Read one published vocabulary word from the assigned curriculum or personal bank."""
    response.headers["Cache-Control"] = "private, no-store"
    return await VocabularyQueryService(db).get_word(user.id, word_id)


@router.post(
    "/practice-sessions",
    status_code=201,
    response_model=VocabPracticeSessionResponse,
    responses={
        200: {
            "description": "Existing active quiz draft reused",
            "model": VocabPracticeSessionResponse,
        }
    },
)
async def create_vocab_practice_session(
    payload: CreateVocabPracticeRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> VocabPracticeSessionResponse:
    """Start or resume the daily vocabulary quiz draft without exposing answer keys."""
    await enforce_rate_limit(
        f"ratelimit:vocab-practice-create:user:{user.id}",
        limit=60,
        window_seconds=3600,
    )
    result, created = await VocabPracticeService(db).create_or_resume(
        user.id, payload.lesson_content_id, idempotency_key
    )
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get(
    "/practice-sessions/{session_id}",
    response_model=VocabPracticeSessionResponse,
    response_model_exclude_none=True,
)
async def get_vocab_practice_session(
    session_id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> VocabPracticeSessionResponse:
    """Read an owned vocabulary quiz session, its saved answers, or its graded result."""
    response.headers["Cache-Control"] = "private, no-store"
    return await VocabPracticeService(db).get_session(user.id, session_id)


@router.patch(
    "/practice-sessions/{session_id}",
    response_model=SaveVocabPracticeAnswersResponse,
)
async def save_vocab_practice_answers(
    session_id: UUID,
    payload: SaveVocabPracticeAnswersRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> SaveVocabPracticeAnswersResponse:
    """Autosave vocabulary quiz answers with edit_version optimistic concurrency."""
    response.headers["Cache-Control"] = "private, no-store"
    return await VocabPracticeService(db).save_answers(user.id, session_id, payload)


@router.post(
    "/practice-sessions/{session_id}/submit",
    status_code=200,
    response_model=SubmitVocabPracticeResponse,
    responses={
        202: {
            "description": "Quiz accepted and contextual AI evaluation queued",
            "model": SubmitVocabPracticeResponse,
        }
    },
)
async def submit_vocab_practice_session(
    session_id: UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
    payload: Annotated[SubmitVocabPracticeRequest | None, Body()] = None,
) -> SubmitVocabPracticeResponse:
    """Grade objective answers, credit the daily lesson once, and queue context AI if needed."""
    await enforce_rate_limit(
        f"ratelimit:vocab-practice-submit:user:{user.id}",
        limit=60,
        window_seconds=3600,
    )
    result = await VocabPracticeService(db).submit(
        user.id, session_id, idempotency_key, payload
    )
    response.status_code = 202 if result.job_id is not None else 200
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get("/reviews/due", response_model=DueReviewsResponse)
async def due_vocab_reviews(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> DueReviewsResponse:
    """Return cursor-paginated due and overdue spaced-repetition vocabulary reviews."""
    response.headers["Cache-Control"] = "private, no-store"
    return await VocabularyQueryService(db).get_due_reviews(
        user.id,
        user.timezone,
        limit=limit,
        cursor=cursor,
    )


@router.post("/reviews", response_model=SubmitVocabReviewResponse)
async def submit_vocab_review(
    payload: SubmitVocabReviewRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> SubmitVocabReviewResponse:
    """Grade one due vocabulary review, record VOCAB_REVIEW submission, and update SRS schedule."""
    await enforce_rate_limit(
        f"ratelimit:vocab-review-submit:user:{user.id}",
        limit=120,
        window_seconds=3600,
    )
    result = await VocabPracticeService(db).submit_review(
        user.id, payload, idempotency_key
    )
    response.headers["Cache-Control"] = "private, no-store"
    return result


@router.get("/bank", response_model=VocabularyBankResponse)
async def vocabulary_bank(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    status: Annotated[VocabularyBankStatus | None, Query()] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=256)] = None,
) -> VocabularyBankResponse:
    """Return cursor-paginated personal vocabulary bank with optional status and search filters."""
    response.headers["Cache-Control"] = "private, no-store"
    return await VocabularyQueryService(db).get_bank(
        user.id,
        status=status,
        search=search,
        limit=limit,
        cursor=cursor,
    )


@router.get("/progress", response_model=VocabularyProgressResponse)
async def vocabulary_progress(
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> VocabularyProgressResponse:
    """Return live vocabulary mastery, due/overdue review counts, and curriculum progress."""
    response.headers["Cache-Control"] = "private, no-store"
    return await VocabularyQueryService(db).get_progress(user.id, user.timezone)



