"""Authenticated assessment endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response

from app.api.deps import CurrentUser, DbSession
from app.infrastructure.cache.redis import enforce_rate_limit
from app.modules.assessment.answers import AnswerService
from app.modules.assessment.results import ResultService
from app.modules.assessment.schemas import (
    AssessmentDetailResponse,
    AssessmentItemResponse,
    AssessmentResultResponse,
    SaveAnswerRequest,
    SaveAnswerResponse,
    StartAssessmentRequest,
    StartAssessmentResponse,
    SubmitAssessmentResponse,
)
from app.modules.assessment.selection import AssignmentService
from app.modules.assessment.service import AssessmentService
from app.modules.assessment.submission import SubmissionService

router = APIRouter(prefix="/assessments", tags=["Assessment"])


@router.get("/{id}", response_model=AssessmentDetailResponse)
async def get_assessment(
    id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> AssessmentDetailResponse:
    response.headers["Cache-Control"] = "no-store"
    return await AssessmentService(db).get(user.id, id)


@router.get(
    "/{id}/current-item",
    response_model=AssessmentItemResponse,
    response_model_exclude_none=True,
    responses={
        204: {"description": "No unanswered item is currently assigned"},
    },
)
async def current_item(id: UUID, user: CurrentUser, db: DbSession, response: Response):
    item = await AssignmentService(db).current_item(user.id, id)
    if item is None:
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.headers["Cache-Control"] = "no-store"
    return item


@router.get(
    "/{id}/result",
    response_model=AssessmentResultResponse,
    responses={
        404: {"description": "Assessment not found or not owned by the current user"},
        503: {"description": "Saved progress or placement is temporarily unavailable"},
    },
)
async def assessment_result(
    id: UUID, user: CurrentUser, db: DbSession, response: Response
) -> AssessmentResultResponse:
    """Poll safe evaluation progress or the completed provisional placement."""
    result = await ResultService(db).get(user.id, id)
    response.headers["Cache-Control"] = "no-store"
    if result.retry_after_seconds is not None:
        response.headers["Retry-After"] = str(result.retry_after_seconds)
    return result


@router.post("/{id}/submit", status_code=202, response_model=SubmitAssessmentResponse)
async def submit_assessment(
    id: UUID,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> SubmitAssessmentResponse:
    await enforce_rate_limit(
        f"ratelimit:assessment-submit:user:{user.id}", limit=60, window_seconds=3600
    )
    result = await SubmissionService(db).submit(user.id, id, idempotency_key)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = result.result_url
    return result


@router.put("/{id}/responses/{response_id}", response_model=SaveAnswerResponse)
async def save_answer(
    id: UUID,
    response_id: UUID,
    payload: SaveAnswerRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
) -> SaveAnswerResponse:
    response.headers["Cache-Control"] = "no-store"
    return await AnswerService(db).save(user.id, id, response_id, payload)


@router.post(
    "/{id}/items/next",
    status_code=201,
    response_model=AssessmentItemResponse,
    response_model_exclude_none=True,
    responses={
        200: {
            "model": AssessmentItemResponse,
            "description": "Existing unanswered item",
        },
        204: {
            "description": "All items have been answered or permitted skips recorded"
        },
    },
)
async def next_item(id: UUID, user: CurrentUser, db: DbSession, response: Response):
    item, created = await AssignmentService(db).next_item(user.id, id)
    if item is None:
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.status_code = 201 if created else 200
    response.headers["Cache-Control"] = "no-store"
    return item


@router.post(
    "",
    status_code=201,
    response_model=StartAssessmentResponse,
    responses={
        200: {
            "model": StartAssessmentResponse,
            "description": "Existing assessment resumed",
        }
    },
)
async def start_assessment(
    payload: StartAssessmentRequest,
    user: CurrentUser,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> StartAssessmentResponse:
    result = await AssessmentService(db).start(user.id, payload, idempotency_key)
    response.status_code = 200 if result.resumed else 201
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = f"/api/v1/assessments/{result.id}"
    return result
