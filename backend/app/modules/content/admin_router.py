"""Authenticated admin batch creation and polling; no inline AI execution."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Response

from app.api.deps import DbSession, require_role
from app.core.config import settings
from app.modules.auth.models import User
from app.modules.content.admin_schemas import (
    BatchProgress,
    CreateBatchRequest,
    RetryBatchRequest,
)
from app.modules.content.admin_service import ContentBatchService
from app.workers.content_tasks import execute_content_generation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/content-generation/batches", tags=["Admin content"])
Admin = Annotated[User, Depends(require_role("ADMIN"))]
_LOCAL_RUNNING_BATCHES: set[str] = set()


async def _run_local_content_batch(batch_key: str, job_ids: list[str]) -> None:
    """Run pending content jobs sequentially in a worker thread when outbox dispatch is disabled locally."""
    if batch_key in _LOCAL_RUNNING_BATCHES:
        return
    _LOCAL_RUNNING_BATCHES.add(batch_key)
    try:
        for job_id in job_ids:
            try:
                await asyncio.to_thread(execute_content_generation, job_id)
            except Exception:  # noqa: BLE001
                logger.exception("local_content_job_failed job_id=%s", job_id)
    finally:
        _LOCAL_RUNNING_BATCHES.discard(batch_key)


def _schedule_local_batch_if_enabled(
    background_tasks: BackgroundTasks, result: BatchProgress
) -> None:
    if (
        settings.environment != "local"
        or settings.outbox_dispatch_enabled
        or not settings.content_generation_enabled
    ):
        return
    pending_ids = [str(c.job_id) for c in result.children if c.status == "PENDING"]
    if pending_ids and result.generation_batch_key not in _LOCAL_RUNNING_BATCHES:
        background_tasks.add_task(
            _run_local_content_batch, result.generation_batch_key, pending_ids
        )


@router.post("", response_model=BatchProgress, status_code=202)
async def create_batch(
    payload: CreateBatchRequest,
    user: Admin,
    db: DbSession,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
):
    result = await ContentBatchService(db).create(user.id, payload, idempotency_key)
    _schedule_local_batch_if_enabled(background_tasks, result)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Location"] = (
        f"/api/v1/admin/content-generation/batches/{result.generation_batch_key}"
    )
    return result


@router.get("/{batch_key}", response_model=BatchProgress)
async def get_batch(
    batch_key: str,
    user: Admin,
    db: DbSession,
    response: Response,
    background_tasks: BackgroundTasks,
):
    response.headers["Cache-Control"] = "private, no-store"
    result = await ContentBatchService(db).get(batch_key)
    _schedule_local_batch_if_enabled(background_tasks, result)
    return result


@router.post("/{batch_key}/retry", response_model=BatchProgress, status_code=202)
async def retry_batch(
    batch_key: str,
    payload: RetryBatchRequest,
    user: Admin,
    db: DbSession,
    response: Response,
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
):
    response.headers["Cache-Control"] = "private, no-store"
    result = await ContentBatchService(db).retry(
        user.id, batch_key, payload, idempotency_key
    )
    _schedule_local_batch_if_enabled(background_tasks, result)
    return result
