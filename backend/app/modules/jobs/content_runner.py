"""Parent/child batch job orchestration and fenced worker runner for Content Factory V1."""

from __future__ import annotations

import hashlib
import random
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError
from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.content.blueprint_loader import get_day_blueprint
from app.modules.content.budget import POLICY
from app.modules.content.contracts import CefrLevel, ContentModule, GoalVariant
from app.modules.jobs.assessment_runner import JobClaim, LostClaimError
from app.modules.jobs.models import AiJob, OutboxEvent

CONTENT_STAGES = {
    "LOADING_CONTEXT",
    "GENERATING_CONTENT",
    "VALIDATING_CONTENT",
    "REVIEWING_QUALITY",
    "SAVING_CONTENT",
}


def default_release_key(
    cefr_level: CefrLevel,
    cycle: int,
    goal_variant: GoalVariant,
    module: ContentModule,
    version: int = 1,
) -> str:
    """Build standard V1 release key: `{CEFR}-C{cycle}-{GOAL}-{MODULE}-v{version}`."""
    return f"{cefr_level}-C{cycle}-{goal_variant}-{module}-v{version}"


async def create_content_generation_batch(
    db: AsyncSession,
    *,
    admin_user_id: UUID | None,
    cefr_level: CefrLevel,
    cycle: int,
    modules: list[ContentModule],
    day_start: int,
    day_end: int,
    goal_variant: GoalVariant = "GENERAL",
    release_keys: dict[ContentModule, str] | None = None,
    blueprint_version: str = "2026.11.1",
    prompt_bundle_version: str = "content-factory-v1",
    idempotency_key: str,
    dry_run: bool = False,
) -> tuple[AiJob, list[AiJob]]:
    """Create parent + child `CONTENT_AUTHORING` jobs and outbox events atomically."""
    if not (1 <= day_start <= day_end <= 21):
        raise ValueError(
            "day_start and day_end must satisfy 1 <= day_start <= day_end <= 21."
        )
    if day_end - day_start >= 5:
        raise ValueError("A batch may contain at most five days.")
    if not modules:
        raise ValueError("At least one module is required.")

    unique_modules = list(dict.fromkeys(modules))
    resolved_releases: dict[ContentModule, str] = {
        mod: (
            release_keys[mod]
            if release_keys and mod in release_keys
            else default_release_key(cefr_level, cycle, goal_variant, mod)
        )
        for mod in unique_modules
    }

    # Validate blueprint coverage for every requested day before writing jobs.
    for day in range(day_start, day_end + 1):
        get_day_blueprint(
            cefr_level,
            cycle,
            day,
            goal_variant=goal_variant,
            blueprint_version=blueprint_version,
        )

    request_context = {
        "cefr_level": cefr_level,
        "cycle": cycle,
        "modules": unique_modules,
        "day_start": day_start,
        "day_end": day_end,
        "goal_variant": goal_variant,
        "release_keys": resolved_releases,
        "blueprint_version": blueprint_version,
        "prompt_bundle_version": prompt_bundle_version,
        "dry_run": dry_run,
    }
    scoped_key = f"{admin_user_id}:{idempotency_key}"
    parent_key = f"content-batch:{hashlib.sha256(scoped_key.encode()).hexdigest()[:48]}"
    existing_parent = await db.scalar(
        select(AiJob).where(AiJob.idempotency_key == parent_key)
    )
    if existing_parent is not None:
        if existing_parent.job_context != request_context:
            raise ConflictError(
                "This idempotency key was used for another request.",
                code="IDEMPOTENCY_CONFLICT",
            )
        existing_children = list(
            await db.scalars(
                select(AiJob)
                .where(AiJob.parent_job_id == existing_parent.id)
                .order_by(AiJob.created_at, AiJob.id)
            )
        )
        return existing_parent, existing_children

    batch_key = f"batch_{uuid4().hex[:16]}"
    parent_job = AiJob(
        id=uuid4(),
        user_id=admin_user_id,
        job_type="CONTENT_AUTHORING",
        status="PENDING",
        stage="WAITING_FOR_WORKER",
        idempotency_key=parent_key,
        prompt_version=prompt_bundle_version,
        generation_batch_key=batch_key,
        job_context={
            "cefr_level": cefr_level,
            "cycle": cycle,
            "modules": unique_modules,
            "day_start": day_start,
            "day_end": day_end,
            "goal_variant": goal_variant,
            "release_keys": resolved_releases,
            "blueprint_version": blueprint_version,
            "prompt_bundle_version": prompt_bundle_version,
            "dry_run": dry_run,
        },
    )
    db.add(parent_job)
    await db.flush()

    children: list[AiJob] = []
    outbox_events: list[OutboxEvent] = []
    for day in range(day_start, day_end + 1):
        for mod in unique_modules:
            child_id = uuid4()
            child_idem = (
                f"content-unit:{batch_key}:{cefr_level}:C{cycle}:D{day:02d}:"
                f"{goal_variant}:{mod}:{prompt_bundle_version}"
            )
            child = AiJob(
                id=child_id,
                user_id=admin_user_id,
                parent_job_id=parent_job.id,
                job_type="CONTENT_AUTHORING",
                status="PENDING",
                stage="WAITING_FOR_WORKER",
                idempotency_key=child_idem,
                prompt_version=prompt_bundle_version,
                generation_batch_key=batch_key,
                job_context={
                    "cefr_level": cefr_level,
                    "cycle": cycle,
                    "day": day,
                    "module": mod,
                    "goal_variant": goal_variant,
                    "release_key": resolved_releases[mod],
                    "blueprint_version": blueprint_version,
                    "prompt_bundle_version": prompt_bundle_version,
                    "dry_run": dry_run,
                    "generation_budget": dict(POLICY),
                },
            )
            children.append(child)
            outbox_events.append(
                OutboxEvent(
                    ai_job_id=child_id,
                    event_type="CONTENT_GENERATION_REQUESTED",
                    payload={
                        "job_id": str(child_id),
                        "parent_job_id": str(parent_job.id),
                        "generation_batch_key": batch_key,
                        "cefr_level": cefr_level,
                        "cycle": cycle,
                        "day": day,
                        "module": mod,
                        "goal_variant": goal_variant,
                        "dry_run": dry_run,
                    },
                )
            )

    db.add_all(children)
    await db.flush()
    db.add_all(outbox_events)
    return parent_job, children


def derive_batch_status(
    child_jobs: list[AiJob],
    item_statuses: list[tuple[str, UUID | None]] | None = None,
) -> str:
    """Derive Admin Studio batch status from child jobs and generated items (Spec Section 13.1)."""
    if not child_jobs:
        return "PENDING"

    statuses = [job.status for job in child_jobs]
    if all(s == "PENDING" for s in statuses):
        return "PENDING"
    if any(s in ("PENDING", "RUNNING", "RETRYABLE") for s in statuses):
        return "RUNNING"
    if any(s == "FAILED" for s in statuses):
        return "GENERATION_FAILED"

    # All child jobs SUCCEEDED
    if not item_statuses:
        return "GENERATION_COMPLETE"

    item_states = [status for status, _ in item_statuses]
    if all(status == "PUBLISHED" for status in item_states):
        return "PUBLISHED"
    if all(
        status == "PUBLISHED" or (status == "REVIEW" and reviewed_by is not None)
        for status, reviewed_by in item_statuses
    ):
        return "READY_TO_PUBLISH"
    if any(reviewed_by is not None for _, reviewed_by in item_statuses):
        return "AWAITING_APPROVAL"
    if any(status == "REVIEW" for status in item_states):
        return "READY_FOR_REVIEW"
    return "GENERATION_COMPLETE"


def _locked_child_job(db, job_id: UUID) -> AiJob | None:
    return db.scalar(
        select(AiJob)
        .where(
            AiJob.id == job_id,
            AiJob.job_type == "CONTENT_AUTHORING",
            AiJob.parent_job_id.is_not(None),
        )
        .with_for_update()
    )


def _fail_or_retry(job: AiJob, now, code: str, retryable: bool) -> None:
    job.claim_token = None
    job.lease_expires_at = None
    job.last_error_code = code
    if retryable and job.attempts < settings.content_job_max_attempts:
        job.status = "RETRYABLE"
        job.stage = "RETRY_SCHEDULED"
        job.next_attempt_at = now + timedelta(
            seconds=min(300, 15 * 2**job.attempts) + random.uniform(0, 5)
        )
    else:
        job.status = "FAILED"
        job.stage = "FAILED"
        job.finished_at = now
        job.next_attempt_at = None


def claim_job(job_id: UUID) -> JobClaim | None:
    """Atomically claim one `CONTENT_AUTHORING` child job for execution."""
    with SyncSessionLocal.begin() as db:
        # Serialize claims across accidentally duplicated worker deployments.
        # The lock is released before generation; the durable lease occupies the slot.
        db.execute(text("SELECT pg_advisory_xact_lock(71503261117)"))
        job = _locked_child_job(db, job_id)
        if job is None:
            return None
        now = db.scalar(select(func.clock_timestamp()))
        if job.status in ("SUCCEEDED", "FAILED"):
            return None
        if job.cancel_requested_at is not None:
            _fail_or_retry(job, now, "CANCELLED", False)
            return None
        if job.status == "RUNNING":
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                _fail_or_retry(job, now, "WORKER_LEASE_EXPIRED", True)
            return None
        if job.next_attempt_at is not None and job.next_attempt_at > now:
            return None
        if job.attempts >= settings.content_job_max_attempts:
            _fail_or_retry(job, now, "MAX_ATTEMPTS_EXCEEDED", False)
            return None
        if db.scalar(
            select(AiJob.id)
            .where(
                AiJob.job_type == "CONTENT_AUTHORING",
                AiJob.parent_job_id.is_not(None),
                AiJob.id != job.id,
                AiJob.status == "RUNNING",
                AiJob.lease_expires_at > now,
            )
            .limit(1)
        ):
            # Delivery can be acknowledged: recovery will enqueue this pending job
            # again after the visibility deadline. No attempt is consumed.
            return None
        job.claim_token = uuid4()
        job.lease_expires_at = now + timedelta(
            seconds=settings.assessment_job_lease_seconds
        )
        job.status = "RUNNING"
        job.stage = "LOADING_CONTEXT"
        job.attempts += 1
        job.started_at = now
        job.next_attempt_at = None
        job.last_error_code = None
        return JobClaim(job.id, job.claim_token)


def require_claim(db, claim: JobClaim):
    job = _locked_child_job(db, claim.job_id)
    now = db.scalar(select(func.clock_timestamp()))
    if (
        job is None
        or job.status != "RUNNING"
        or job.claim_token != claim.token
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise LostClaimError()
    return job, now


def report_stage(claim: JobClaim, stage: str) -> None:
    if stage not in CONTENT_STAGES:
        raise ValueError(f"Unknown content generation stage: {stage}")
    with SyncSessionLocal.begin() as db:
        job, _ = require_claim(db, claim)
        job.stage = stage


def finish_job(
    claim: JobClaim,
    *,
    result_summary: dict,
    metrics: dict | None = None,
    model: str | None = None,
    langsmith_run_id: str | None = None,
) -> None:
    with SyncSessionLocal.begin() as db:
        job, now = require_claim(db, claim)
        job.status = "SUCCEEDED"
        job.stage = "DONE"
        job.finished_at = now
        job.claim_token = None
        job.lease_expires_at = None
        job.result_summary = result_summary
        if metrics is not None:
            job.metrics = {**(job.metrics or {}), **metrics}
        if model is not None:
            job.model = model
        if langsmith_run_id is not None:
            job.langsmith_run_id = str(langsmith_run_id)[:80]


def fail_job(claim: JobClaim, *, retryable: bool, code: str) -> None:
    with SyncSessionLocal.begin() as db:
        job, now = require_claim(db, claim)
        _fail_or_retry(job, now, code, retryable)


def recover_job(job_id: UUID) -> bool:
    """Recover only child jobs; preserve quarantined deliveries for operators."""
    if not settings.content_generation_enabled:
        return False
    with SyncSessionLocal.begin() as db:
        job = _locked_child_job(db, job_id)
        if job is None or job.status in ("SUCCEEDED", "FAILED"):
            return False
        now = db.scalar(select(func.clock_timestamp()))
        if job.status == "RUNNING":
            if job.lease_expires_at is not None and job.lease_expires_at > now:
                return False
            _fail_or_retry(job, now, "WORKER_LEASE_EXPIRED", True)
            return True
        if job.status not in ("PENDING", "RETRYABLE"):
            return False
        if job.cancel_requested_at is not None:
            _fail_or_retry(job, now, "CANCELLED", False)
            return True
        if job.next_attempt_at is not None and job.next_attempt_at > now:
            return False
        if job.attempts >= settings.content_job_max_attempts:
            _fail_or_retry(job, now, "MAX_ATTEMPTS_EXCEEDED", False)
            return True
        if db.scalar(
            select(OutboxEvent.id)
            .where(
                OutboxEvent.ai_job_id == job.id,
                OutboxEvent.published_at.is_(None),
            )
            .limit(1)
        ):
            return False
        latest = db.scalar(
            select(func.max(OutboxEvent.published_at)).where(
                OutboxEvent.ai_job_id == job.id,
            )
        )
        if job.status == "PENDING" and (
            (latest or job.created_at)
            + timedelta(seconds=settings.celery_visibility_timeout)
            > now
        ):
            return False
        db.add(
            OutboxEvent(
                ai_job_id=job.id,
                event_type="CONTENT_GENERATION_REQUESTED",
                payload={
                    "job_id": str(job.id),
                    "parent_job_id": str(job.parent_job_id),
                    "generation_batch_key": job.generation_batch_key,
                },
            )
        )
        job.status = "PENDING"
        job.stage = "WAITING_FOR_WORKER"
        job.next_attempt_at = None
        return True
