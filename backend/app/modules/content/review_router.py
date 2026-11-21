"""Authenticated admin endpoints for inspecting and approving generated ContentItems."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import DbSession, require_role
from app.modules.auth.models import User
from app.modules.content.review_schemas import (
    ContentItemDetail,
    ContentItemListResponse,
    ReviewDecisionRequest,
)
from app.modules.content.review_service import ContentReviewService

router = APIRouter(prefix="/admin/content", tags=["Admin content review"])
Admin = Annotated[User, Depends(require_role("ADMIN"))]


@router.get("/items", response_model=ContentItemListResponse)
async def list_content_items(
    user: Admin,
    db: DbSession,
    response: Response,
    status: str | None = Query(default=None),
    release_key: str | None = Query(default=None),
    generation_batch_key: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> ContentItemListResponse:
    response.headers["Cache-Control"] = "private, no-store"
    return await ContentReviewService(db).list_items(
        status=status,
        release_key=release_key,
        generation_batch_key=generation_batch_key,
        kind=kind,
        origin=origin,
        limit=limit,
    )


@router.get("/items/{item_id}", response_model=ContentItemDetail)
async def get_content_item(
    item_id: UUID,
    user: Admin,
    db: DbSession,
    response: Response,
) -> ContentItemDetail:
    response.headers["Cache-Control"] = "private, no-store"
    return await ContentReviewService(db).get_detail(item_id)


@router.post("/items/{item_id}/decision", response_model=ContentItemDetail)
async def decide_content_item(
    item_id: UUID,
    payload: ReviewDecisionRequest,
    user: Admin,
    db: DbSession,
    response: Response,
) -> ContentItemDetail:
    response.headers["Cache-Control"] = "private, no-store"
    return await ContentReviewService(db).apply_decision(user.id, item_id, payload)
