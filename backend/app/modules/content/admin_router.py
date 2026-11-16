"""Authenticated admin batch creation and polling; no inline AI execution."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from app.api.deps import DbSession, require_role
from app.modules.auth.models import User
from app.modules.content.admin_schemas import (
    BatchProgress,
    CreateBatchRequest,
    RetryBatchRequest,
)
from app.modules.content.admin_service import ContentBatchService

router = APIRouter(prefix="/admin/content-generation/batches", tags=["Admin content"])
Admin = Annotated[User, Depends(require_role("ADMIN"))]


@router.post("", response_model=BatchProgress, status_code=202)
async def create_batch(
    payload: CreateBatchRequest,
    user: Admin,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
):
    result = await ContentBatchService(db).create(user.id, payload, idempotency_key)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Location"] = (
        f"/api/v1/admin/content-generation/batches/{result.generation_batch_key}"
    )
    return result


@router.get("/{batch_key}", response_model=BatchProgress)
async def get_batch(batch_key: str, user: Admin, db: DbSession, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return await ContentBatchService(db).get(batch_key)


@router.post("/{batch_key}/retry", response_model=BatchProgress, status_code=202)
async def retry_batch(
    batch_key: str,
    payload: RetryBatchRequest,
    user: Admin,
    db: DbSession,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
):
    response.headers["Cache-Control"] = "private, no-store"
    return await ContentBatchService(db).retry(
        user.id, batch_key, payload, idempotency_key
    )
