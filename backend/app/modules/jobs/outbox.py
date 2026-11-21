"""Durable outbox claims and fenced publication acknowledgement."""

import random
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.jobs.models import AiJob, OutboxEvent


@dataclass(frozen=True)
class DispatchClaim:
    event_id: UUID
    token: UUID
    job_id: UUID
    job_type: str = "ASSESSMENT"


def claim_next() -> DispatchClaim | None:
    event_types = []
    if settings.assessment_execution_enabled:
        event_types.append("EVALUATION_REQUESTED")
    if settings.speaking_execution_enabled:
        event_types.append("SPEAKING_FEEDBACK_REQUESTED")
    if settings.vocabulary_execution_enabled:
        event_types.append("VOCAB_CONTEXT_REQUESTED")
    if settings.writing_execution_enabled:
        event_types.append("WRITING_FEEDBACK_REQUESTED")
    if settings.content_generation_enabled:
        event_types.append("CONTENT_GENERATION_REQUESTED")
    earlier = aliased(AiJob)
    running_content = aliased(AiJob)
    # Start curriculum days in order, even when event UUIDs sort differently.
    # Once an earlier day has been attempted, its failure/backoff does not block siblings.
    earlier_unstarted = (
        select(earlier.id)
        .where(
            earlier.parent_job_id == AiJob.parent_job_id,
            earlier.job_type == "CONTENT_AUTHORING",
            earlier.status == "PENDING",
            earlier.attempts == 0,
            earlier.job_context["day"].as_integer()
            < AiJob.job_context["day"].as_integer(),
        )
        .exists()
    )
    blocked_content = (
        select(AiJob.id)
        .where(
            AiJob.id == OutboxEvent.ai_job_id,
            earlier_unstarted,
        )
        .exists()
    )
    # Do not publish another content job while one already holds an active worker lease;
    # otherwise claim_job() would skip and drop it until the visibility timeout expires.
    active_content_running = (
        select(running_content.id)
        .where(
            running_content.job_type == "CONTENT_AUTHORING",
            running_content.parent_job_id.is_not(None),
            running_content.status == "RUNNING",
            running_content.lease_expires_at > func.now(),
        )
        .exists()
    )
    with SyncSessionLocal.begin() as db:
        now = db.scalar(select(func.now()))
        event = db.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.event_type.in_(event_types),
                or_(
                    OutboxEvent.event_type != "CONTENT_GENERATION_REQUESTED",
                    (~blocked_content) & (~active_content_running),
                ),
                OutboxEvent.published_at.is_(None),
                OutboxEvent.failed_at.is_(None),
                or_(
                    OutboxEvent.next_attempt_at.is_(None),
                    OutboxEvent.next_attempt_at <= now,
                ),
                or_(
                    OutboxEvent.lease_expires_at.is_(None),
                    OutboxEvent.lease_expires_at <= now,
                ),
            )
            .order_by(OutboxEvent.created_at, OutboxEvent.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if event is None:
            return None
        # A crashed claim consumes an attempt too; quarantine exhausted events.
        if event.attempt_count >= settings.outbox_max_attempts:
            event.failed_at = now
            event.last_error_code = "DELIVERY_ATTEMPTS_EXHAUSTED"
            event.claim_token = None
            event.lease_expires_at = None
            return None
        job = db.get(AiJob, event.ai_job_id) if event.ai_job_id else None
        payload = event.payload
        valid_binding = (
            job is not None
            and isinstance(payload, dict)
            and (
                (
                    event.event_type == "CONTENT_GENERATION_REQUESTED"
                    and job.job_type == "CONTENT_AUTHORING"
                    and job.parent_job_id is not None
                    and job.generation_batch_key is not None
                    and payload.get("parent_job_id") == str(job.parent_job_id)
                    and payload.get("generation_batch_key") == job.generation_batch_key
                )
                or (
                    event.event_type == "EVALUATION_REQUESTED"
                    and job.job_type == "ASSESSMENT"
                    and job.assessment_attempt_id is not None
                    and payload.get("assessment_attempt_id")
                    == str(job.assessment_attempt_id)
                )
                or (
                    event.event_type == "SPEAKING_FEEDBACK_REQUESTED"
                    and job.job_type == "SPEAKING_FEEDBACK"
                    and job.practice_submission_id is not None
                    and payload.get("practice_submission_id")
                    == str(job.practice_submission_id)
                )
                or (
                    event.event_type == "VOCAB_CONTEXT_REQUESTED"
                    and job.job_type == "VOCAB_CONTEXT"
                    and job.practice_submission_id is not None
                    and payload.get("practice_submission_id")
                    == str(job.practice_submission_id)
                )
                or (
                    event.event_type == "WRITING_FEEDBACK_REQUESTED"
                    and job.job_type == "WRITING_FEEDBACK"
                    and job.practice_submission_id is not None
                    and payload.get("practice_submission_id")
                    == str(job.practice_submission_id)
                )
            )
        )
        if (
            job is None
            or not valid_binding
            or not isinstance(payload, dict)
            or payload.get("job_id") != str(job.id)
        ):
            event.failed_at = now
            event.last_error_code = "INVALID_EVALUATION_EVENT"
            return None
        token = uuid4()
        event.claim_token = token
        event.lease_expires_at = now + timedelta(seconds=settings.outbox_lease_seconds)
        event.attempt_count += 1
        return DispatchClaim(event.id, token, job.id, job.job_type)


def mark_published(claim: DispatchClaim) -> bool:
    with SyncSessionLocal.begin() as db:
        result = db.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == claim.event_id,
                OutboxEvent.claim_token == claim.token,
                OutboxEvent.published_at.is_(None),
            )
            .values(
                published_at=func.now(),
                claim_token=None,
                lease_expires_at=None,
                next_attempt_at=None,
                last_error_code=None,
            )
        )
        return result.rowcount == 1


def record_failure(claim: DispatchClaim) -> None:
    with SyncSessionLocal.begin() as db:
        event = db.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.id == claim.event_id,
                OutboxEvent.claim_token == claim.token,
                OutboxEvent.published_at.is_(None),
            )
            .with_for_update()
        )
        if event is None:
            return
        now = db.scalar(select(func.now()))
        event.claim_token = None
        event.lease_expires_at = None
        event.last_error_code = "BROKER_PUBLISH_FAILED"
        if event.attempt_count >= settings.outbox_max_attempts:
            event.failed_at = now
        else:
            delay = min(300, 2 ** min(event.attempt_count, 8)) + random.uniform(0, 3)
            event.next_attempt_at = now + timedelta(seconds=delay)
