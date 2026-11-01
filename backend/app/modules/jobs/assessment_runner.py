"""Fenced assessment execution; provider calls run outside database transactions."""

import random
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.core.config import settings
from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.assessment.models import AssessmentAttempt
from app.modules.assessment.schemas import PublicPlacement
from app.modules.auth.models import User
from app.modules.jobs.models import AiJob, OutboxEvent

STAGES = {
    "TRANSCRIBING_AUDIO",
    "EVALUATING_LANGUAGE",
    "DETERMINING_PLACEMENT",
    "SAVING_RESULTS",
}


class RetryableEvaluationError(Exception):
    """Evaluator raises this only for a transient failure safe to retry."""


class LostClaimError(Exception):
    """Execution no longer owns the job; discard its work."""


@dataclass(frozen=True)
class JobClaim:
    job_id: UUID
    token: UUID


def locked_job(db, job_id: UUID):
    identity = db.execute(
        select(AiJob.user_id, AiJob.assessment_attempt_id).where(
            AiJob.id == job_id, AiJob.job_type == "ASSESSMENT"
        )
    ).one_or_none()
    if (
        identity is None
        or identity.user_id is None
        or identity.assessment_attempt_id is None
    ):
        return None
    user = db.scalar(select(User).where(User.id == identity.user_id).with_for_update())
    attempt = db.scalar(
        select(AssessmentAttempt)
        .where(
            AssessmentAttempt.id == identity.assessment_attempt_id,
            AssessmentAttempt.user_id == identity.user_id,
        )
        .with_for_update()
    )
    job = db.scalar(
        select(AiJob)
        .where(AiJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or attempt is None or job is None:
        return None
    return user, attempt, job


def fail_or_retry(db, attempt, job, now, code: str, retryable: bool) -> None:
    job.claim_token = None
    job.lease_expires_at = None
    job.last_error_code = code
    if retryable and job.attempts < settings.assessment_job_max_attempts:
        job.status = "RETRYABLE"
        attempt.status = "FAILED_RETRYABLE"
        job.next_attempt_at = now + timedelta(
            seconds=min(300, 15 * 2**job.attempts) + random.uniform(0, 5)
        )
    else:
        job.status = "FAILED"
        attempt.status = "FAILED_FINAL"
        job.finished_at = now
        job.next_attempt_at = None


def claim_job(job_id: UUID) -> JobClaim | None:
    with SyncSessionLocal.begin() as db:
        records = locked_job(db, job_id)
        if records is None:
            return None
        user, attempt, job = records
        now = db.scalar(select(func.clock_timestamp()))
        if job.status in ("SUCCEEDED", "FAILED") or attempt.status in (
            "COMPLETED",
            "FAILED_FINAL",
        ):
            return None
        if job.status == "RUNNING":
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                fail_or_retry(db, attempt, job, now, "WORKER_LEASE_EXPIRED", True)
            return None
        if job.next_attempt_at is not None and job.next_attempt_at > now:
            return None
        if (
            not user.is_active
            or attempt.status not in ("SUBMITTED", "FAILED_RETRYABLE")
            or job.attempts >= settings.assessment_job_max_attempts
        ):
            fail_or_retry(db, attempt, job, now, "JOB_NOT_ELIGIBLE", False)
            return None
        job.claim_token = uuid4()
        job.lease_expires_at = now + timedelta(
            seconds=settings.assessment_job_lease_seconds
        )
        job.status = "RUNNING"
        job.stage = "EVALUATING_LANGUAGE"
        job.attempts += 1
        job.started_at = now
        job.next_attempt_at = None
        job.last_error_code = None
        attempt.status = "PROCESSING"
        return JobClaim(job.id, job.claim_token)


def require_claim(db, claim: JobClaim):
    records = locked_job(db, claim.job_id)
    now = db.scalar(select(func.clock_timestamp()))
    if records is None:
        raise LostClaimError()
    user, attempt, job = records
    if (
        job.status != "RUNNING"
        or job.claim_token != claim.token
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
        or attempt.status != "PROCESSING"
    ):
        raise LostClaimError()
    return user, attempt, job, now


def report_stage(claim: JobClaim, stage: str) -> None:
    if stage not in STAGES:
        raise ValueError("Unknown evaluation stage")
    with SyncSessionLocal.begin() as db:
        _, _, job, _ = require_claim(db, claim)
        job.stage = stage
        # Fixed execution lease: provider/graph code cannot extend indefinitely.


def finish(
    claim: JobClaim,
    result: PublicPlacement,
    *,
    langsmith_run_id: str | None = None,
) -> None:
    trace_id = langsmith_run_id or getattr(result, "_langsmith_run_id", None)
    result = PublicPlacement.model_validate(
        result.model_dump() if isinstance(result, PublicPlacement) else result
    )
    if not result.skills.writing.assessed:
        raise ValueError("Required writing evidence is unavailable")
    with SyncSessionLocal.begin() as db:
        user, attempt, job, now = require_claim(db, claim)
        if not user.is_active:
            fail_or_retry(db, attempt, job, now, "ACCOUNT_INACTIVE", False)
            return
        attempt.result = result.model_dump(mode="json")
        attempt.placement_cefr = result.cefr
        attempt.confidence = result.confidence
        attempt.completed_at = now
        attempt.status = "COMPLETED"
        job.status = "SUCCEEDED"
        job.stage = "DONE"
        job.finished_at = now
        job.rubric_version = result.rubric_version
        job.model = settings.openai_evaluation_model
        if trace_id:
            job.langsmith_run_id = str(trace_id)[:80]
        job.claim_token = None
        job.lease_expires_at = None
        newer = db.scalar(
            select(AssessmentAttempt.id)
            .where(
                AssessmentAttempt.user_id == user.id,
                AssessmentAttempt.kind == "INITIAL",
                AssessmentAttempt.started_at > attempt.started_at,
            )
            .limit(1)
        )
        if newer is None and user.onboarding_status != "COMPLETED":
            user.onboarding_status = "RESULT_READY"


def fail(claim: JobClaim, *, retryable: bool, code: str) -> None:
    with SyncSessionLocal.begin() as db:
        _, attempt, job, now = require_claim(db, claim)
        fail_or_retry(db, attempt, job, now, code, retryable)


def recover_job(job_id: UUID) -> bool:
    with SyncSessionLocal.begin() as db:
        records = locked_job(db, job_id)
        if records is None:
            return False
        _, attempt, job = records
        now = db.scalar(select(func.clock_timestamp()))
        if job.status == "RUNNING":
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                fail_or_retry(db, attempt, job, now, "WORKER_LEASE_EXPIRED", True)
                return True
            return False
        if job.status not in ("PENDING", "RETRYABLE"):
            return False
        if job.next_attempt_at is not None and job.next_attempt_at > now:
            return False
        # Never reset a live/failed outbox event; failed delivery needs operator review.
        unpublished = db.scalar(
            select(OutboxEvent.id)
            .where(OutboxEvent.ai_job_id == job.id, OutboxEvent.published_at.is_(None))
            .limit(1)
        )
        if unpublished is not None:
            return False
        latest_publish = db.scalar(
            select(func.max(OutboxEvent.published_at)).where(
                OutboxEvent.ai_job_id == job.id
            )
        )
        if (
            job.status == "PENDING"
            and (latest_publish or job.created_at)
            + timedelta(seconds=settings.celery_visibility_timeout)
            > now
        ):
            return False
        db.add(
            OutboxEvent(
                ai_job_id=job.id,
                event_type="EVALUATION_REQUESTED",
                payload={
                    "job_id": str(job.id),
                    "assessment_attempt_id": str(attempt.id),
                },
            )
        )
        job.status = "PENDING"
        job.stage = "WAITING_FOR_WORKER"
        job.next_attempt_at = None
        attempt.status = "SUBMITTED"
        return True
