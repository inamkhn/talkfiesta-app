"""Admin transactions for the five-day vocabulary pilot."""

import hashlib
import json
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.content.admin_schemas import (
    BatchProgress,
    ChildProgress,
    CreateBatchRequest,
    RetryBatchRequest,
)
from app.modules.content.budget import remaining_calls
from app.modules.content.models import ContentItem
from app.modules.jobs.content_runner import (
    create_content_generation_batch,
    derive_batch_status,
)
from app.modules.jobs.models import AiJob, OutboxEvent


def project_batch(parent: AiJob, children: list[AiJob]) -> BatchProgress:
    context = parent.job_context
    return BatchProgress(
        generation_batch_key=parent.generation_batch_key,
        parent_job_id=parent.id,
        # This is generation status, never a claim that a release is publishable.
        status=derive_batch_status(children),
        release_key=context["release_keys"]["VOCABULARY"],
        dry_run=context["dry_run"],
        child_job_count=len(children),
        children=[
            ChildProgress(
                job_id=job.id,
                day=job.job_context["day"],
                status=job.status,
                stage=job.stage,
                attempts=job.attempts or 0,
                error_code=job.last_error_code,
                lesson_id=(job.result_summary or {}).get("lesson_id"),
                item_status=(job.result_summary or {}).get("item_status"),
                provider_calls_reserved=(job.metrics or {}).get(
                    "provider_calls_reserved", 0
                ),
                remaining_provider_calls=remaining_calls(job),
                input_tokens=(job.metrics or {}).get("input_tokens", 0),
                output_tokens=(job.metrics or {}).get("output_tokens", 0),
            )
            for job in sorted(children, key=lambda job: job.job_context["day"])
        ],
    )


class ContentBatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def retry(
        self, admin_id: UUID, batch_key: str, request: RetryBatchRequest, key: str
    ):
        try:
            parent = await self.db.scalar(
                select(AiJob)
                .where(
                    AiJob.generation_batch_key == batch_key,
                    AiJob.job_type == "CONTENT_AUTHORING",
                    AiJob.parent_job_id.is_(None),
                )
                .with_for_update()
            )
            if parent is None:
                raise NotFoundError("Content batch not found.")
            children = list(
                await self.db.scalars(
                    select(AiJob)
                    .where(
                        AiJob.parent_job_id == parent.id,
                    )
                    .order_by(AiJob.id)
                    .with_for_update()
                )
            )
            receipt_key = hashlib.sha256(f"{admin_id}:{key}".encode()).hexdigest()
            fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "ids": sorted(str(i) for i in request.child_job_ids),
                        "reason": request.reason,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            metrics = dict(parent.metrics or {})
            receipts = dict(metrics.get("retry_receipts", {}))
            if receipt_key in receipts:
                if receipts[receipt_key]["fingerprint"] != fingerprint:
                    raise ConflictError(
                        "This retry key was used for another request.",
                        code="IDEMPOTENCY_CONFLICT",
                    )
            else:
                selected = [job for job in children if job.id in request.child_job_ids]
                if len(selected) != len(request.child_job_ids):
                    raise NotFoundError("A selected job does not belong to this batch.")
                for job in selected:
                    if (
                        job.status != "FAILED"
                        or job.cancel_requested_at is not None
                        or job.attempts >= settings.content_job_max_attempts
                        or remaining_calls(job) == 0
                    ):
                        raise ConflictError(
                            "Select failed jobs with remaining attempt and generation budgets.",
                            code="CONTENT_RETRY_NOT_ALLOWED",
                        )
                    if await self.db.scalar(
                        select(OutboxEvent.id)
                        .where(
                            OutboxEvent.ai_job_id == job.id,
                            OutboxEvent.published_at.is_(None),
                        )
                        .limit(1)
                    ):
                        raise ConflictError(
                            "An undelivered event requires dispatcher or operator handling.",
                            code="CONTENT_DELIVERY_PENDING",
                        )
                for job in selected:
                    job.status = "PENDING"
                    job.stage = "WAITING_FOR_WORKER"
                    job.next_attempt_at = job.finished_at = None
                    job.claim_token = job.lease_expires_at = None
                    self.db.add(
                        OutboxEvent(
                            ai_job_id=job.id,
                            event_type="CONTENT_GENERATION_REQUESTED",
                            payload={
                                "job_id": str(job.id),
                                "parent_job_id": str(parent.id),
                                "generation_batch_key": batch_key,
                            },
                        )
                    )
                receipts[receipt_key] = {
                    "fingerprint": fingerprint,
                    "admin_id": str(admin_id),
                    "reason": request.reason,
                    "job_ids": [str(j.id) for j in selected],
                }
                parent.metrics = {**metrics, "retry_receipts": receipts}
            result = project_batch(parent, children)
            await self.db.commit()
            return result
        except Exception:
            await self.db.rollback()
            raise

    async def create(self, admin_id: UUID, request: CreateBatchRequest, key: str):
        try:
            # A short global authoring lock serializes admin creates across accounts.
            # No provider call or queue publication occurs in this transaction.
            await self.db.execute(text("SELECT pg_advisory_xact_lock(71503261116)"))
            parent, children = await create_content_generation_batch(
                self.db,
                admin_user_id=admin_id,
                cefr_level=request.cefr_level,
                cycle=request.cycle,
                modules=[request.module],
                day_start=request.day_start,
                day_end=request.day_end,
                goal_variant=request.goal_variant,
                release_keys={request.module: request.release_key},
                idempotency_key=key,
                dry_run=request.dry_run,
            )
            if not request.dry_run:
                # A prior failed unit still owns its slot; retry that unit instead.
                conflict = await self.db.scalar(
                    select(AiJob.id)
                    .where(
                        AiJob.job_type == "CONTENT_AUTHORING",
                        AiJob.parent_job_id.is_not(None),
                        AiJob.parent_job_id != parent.id,
                        AiJob.job_context["release_key"].astext == request.release_key,
                        AiJob.job_context["dry_run"].as_boolean() == False,
                        AiJob.job_context["day"]
                        .as_integer()
                        .between(request.day_start, request.day_end),
                    )
                    .limit(1)
                )
                existing_content = await self.db.scalar(
                    select(ContentItem.id)
                    .where(
                        ContentItem.release_key == request.release_key,
                        ContentItem.day.between(request.day_start, request.day_end),
                        ContentItem.kind == "VOCABULARY_LESSON",
                        ContentItem.generation_batch_key.is_distinct_from(
                            parent.generation_batch_key
                        ),
                    )
                    .limit(1)
                )
                if conflict or existing_content:
                    raise ConflictError(
                        "These release days already have content or a generation job.",
                        code="CONTENT_DAYS_RESERVED",
                    )
            result = project_batch(parent, children)
            await self.db.commit()
            return result
        except Exception:
            await self.db.rollback()
            raise

    async def get(self, batch_key: str):
        parent = await self.db.scalar(
            select(AiJob).where(
                AiJob.generation_batch_key == batch_key,
                AiJob.job_type == "CONTENT_AUTHORING",
                AiJob.parent_job_id.is_(None),
            )
        )
        if parent is None:
            raise NotFoundError("Content batch not found.")
        children = list(
            await self.db.scalars(select(AiJob).where(AiJob.parent_job_id == parent.id))
        )
        return project_batch(parent, children)
