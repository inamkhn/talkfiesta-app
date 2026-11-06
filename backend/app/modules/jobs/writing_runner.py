"""Fenced Writing feedback runner; completion credits are never modified here."""

from __future__ import annotations

import hashlib
import json
import random
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.core.config import settings
from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.jobs.assessment_runner import JobClaim, LostClaimError
from app.modules.jobs.models import AiJob, OutboxEvent
from app.modules.practice.models import PracticeSubmission
from app.modules.writing.schemas import WritingFeedbackReport

WRITING_RUBRIC_VERSION = "writing-rubric-v1"
RUNNING_STAGES = {"EVALUATING_WRITING", "COMPARING_REVISION", "SAVING_RESULTS"}


def locked_job(db, job_id: UUID):
    identity = db.execute(
        select(AiJob.user_id, AiJob.practice_submission_id).where(
            AiJob.id == job_id, AiJob.job_type == "WRITING_FEEDBACK"
        )
    ).one_or_none()
    if identity is None or identity.user_id is None:
        return None
    user = db.scalar(select(User).where(User.id == identity.user_id).with_for_update())
    submission = db.scalar(
        select(PracticeSubmission)
        .where(
            PracticeSubmission.id == identity.practice_submission_id,
            PracticeSubmission.user_id == identity.user_id,
            PracticeSubmission.mode == "WRITING",
        )
        .with_for_update()
    )
    job = db.scalar(select(AiJob).where(AiJob.id == job_id).with_for_update())
    if user is None or submission is None or job is None:
        return None
    return user, submission, job


def fail_or_retry(submission, job, now, code: str, retryable: bool) -> None:
    job.claim_token = None
    job.lease_expires_at = None
    job.last_error_code = code
    if retryable and job.attempts < settings.writing_job_max_attempts:
        job.status = "RETRYABLE"
        job.stage = "RETRY_SCHEDULED"
        job.next_attempt_at = now + timedelta(
            seconds=min(300, 15 * 2**job.attempts) + random.uniform(0, 5)
        )
        submission.evaluation_status = "PENDING"
    else:
        job.status = "FAILED"
        job.stage = "FAILED"
        job.finished_at = now
        job.next_attempt_at = None
        submission.evaluation_status = "FAILED"


def claim_job(job_id: UUID) -> JobClaim | None:
    with SyncSessionLocal.begin() as db:
        records = locked_job(db, job_id)
        if records is None:
            return None
        user, submission, job = records
        now = db.scalar(select(func.clock_timestamp()))
        if job.status in ("SUCCEEDED", "FAILED"):
            return None
        if job.status == "RUNNING":
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                fail_or_retry(submission, job, now, "WORKER_LEASE_EXPIRED", True)
            return None
        if job.next_attempt_at is not None and job.next_attempt_at > now:
            return None
        if (
            not user.is_active
            or submission.status != "ACCEPTED"
            or job.attempts >= settings.writing_job_max_attempts
        ):
            fail_or_retry(submission, job, now, "JOB_NOT_ELIGIBLE", False)
            return None
        job.status = "RUNNING"
        job.stage = "EVALUATING_WRITING"
        job.claim_token = uuid4()
        job.lease_expires_at = now + timedelta(
            seconds=settings.assessment_job_lease_seconds
        )
        job.attempts += 1
        job.started_at = now
        job.next_attempt_at = None
        job.last_error_code = None
        submission.evaluation_status = "PROCESSING"
        return JobClaim(job.id, job.claim_token)


def require_claim(db, claim: JobClaim):
    records = locked_job(db, claim.job_id)
    now = db.scalar(select(func.clock_timestamp()))
    if records is None:
        raise LostClaimError()
    user, submission, job = records
    if (
        job.status != "RUNNING"
        or job.claim_token != claim.token
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
        or submission.status != "ACCEPTED"
        or submission.evaluation_status != "PROCESSING"
    ):
        raise LostClaimError()
    return user, submission, job, now


def snapshot(db, submission: PracticeSubmission) -> tuple[dict, str]:
    prompt_item = db.get(ContentItem, submission.content_item_id)
    raw_input = submission.input
    if (
        prompt_item is None
        or not isinstance(raw_input, dict)
        or prompt_item.module != "WRITING"
        or prompt_item.kind != "WRITING_LESSON"
        or prompt_item.status not in ("PUBLISHED", "ARCHIVED")
        or not isinstance(prompt_item.body, dict)
    ):
        raise ValueError("Frozen writing submission evidence is inconsistent")

    submitted_text = raw_input.get("text")
    if not isinstance(submitted_text, str) or not submitted_text.strip():
        raise ValueError("Submitted writing text is missing")

    previous_version: dict | None = None
    if submission.revision_number > 1 and submission.revision_group_id is not None:
        prev_row = db.scalar(
            select(PracticeSubmission).where(
                PracticeSubmission.user_id == submission.user_id,
                PracticeSubmission.mode == "WRITING",
                PracticeSubmission.revision_group_id == submission.revision_group_id,
                PracticeSubmission.revision_number == submission.revision_number - 1,
            )
        )
        if prev_row is not None:
            prev_inp = prev_row.input if isinstance(prev_row.input, dict) else {}
            prev_fb = prev_row.feedback if isinstance(prev_row.feedback, dict) else {}
            prev_report = (
                prev_fb.get("report")
                if isinstance(prev_fb.get("report"), dict)
                else prev_fb
            )
            previous_version = {
                "revision_number": prev_row.revision_number,
                "text": str(prev_inp.get("text", "")),
                "corrections": (
                    prev_report.get("corrections")
                    if isinstance(prev_report, dict)
                    else []
                ),
                "improvements": (
                    prev_report.get("improvements")
                    if isinstance(prev_report, dict)
                    else []
                ),
            }

    evidence = {
        "submission_id": str(submission.id),
        "revision_number": submission.revision_number,
        "title": prompt_item.title,
        "target_cefr": prompt_item.cefr_level,
        "writing_type": prompt_item.body.get("writing_type"),
        "instructions": prompt_item.body.get("instructions"),
        "target_word_count": prompt_item.body.get("target_word_count"),
        "minimum_word_count": prompt_item.body.get("minimum_word_count"),
        "maximum_word_count": prompt_item.body.get("maximum_word_count"),
        "submitted_text": submitted_text,
        "previous_version": previous_version,
    }
    fingerprint = hashlib.sha256(
        json.dumps(evidence, sort_keys=True).encode()
    ).hexdigest()
    return evidence, fingerprint


def load_evidence(claim: JobClaim) -> tuple[dict, str]:
    with SyncSessionLocal.begin() as db:
        user, submission, job, _ = require_claim(db, claim)
        if not user.is_active:
            raise ValueError("Account inactive")
        evidence, fingerprint = snapshot(db, submission)
        metrics = job.metrics or {}
        if metrics.get("evidence_fingerprint", fingerprint) != fingerprint:
            raise ValueError("Frozen writing evidence changed between attempts")
        job.metrics = {**metrics, "evidence_fingerprint": fingerprint}
        return evidence, fingerprint


def report_stage(claim: JobClaim, stage: str) -> None:
    if stage not in RUNNING_STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    with SyncSessionLocal.begin() as db:
        _, _, job, _ = require_claim(db, claim)
        job.stage = stage


def finish(
    claim: JobClaim,
    fingerprint: str,
    feedback: WritingFeedbackReport,
    trace_id: str | UUID,
) -> None:
    validated = WritingFeedbackReport.model_validate(feedback.model_dump())
    with SyncSessionLocal.begin() as db:
        user, submission, job, now = require_claim(db, claim)
        evidence, current_fp = snapshot(db, submission)
        if not user.is_active or current_fp != fingerprint:
            raise ValueError("Frozen writing evidence changed")
        submitted_text = evidence["submitted_text"]
        if any(c.original not in submitted_text for c in validated.corrections):
            raise ValueError("Corrections must quote the original submitted text")
        if job.lease_expires_at <= db.scalar(select(func.clock_timestamp())):
            raise LostClaimError()

        existing_fb = (
            dict(submission.feedback) if isinstance(submission.feedback, dict) else {}
        )
        report_json = validated.model_dump(mode="json")
        existing_fb["report"] = report_json
        existing_fb.update(report_json)
        submission.feedback = existing_fb
        submission.score = Decimal(validated.scores.overall).quantize(Decimal("0.01"))
        submission.evaluation_status = "COMPLETED"

        job.status = "SUCCEEDED"
        job.stage = "DONE"
        job.finished_at = now
        job.rubric_version = WRITING_RUBRIC_VERSION
        job.prompt_version = WRITING_RUBRIC_VERSION
        job.model = settings.openai_evaluation_model
        job.langsmith_run_id = str(trace_id)
        job.claim_token = None
        job.lease_expires_at = None


def fail(claim: JobClaim, retryable: bool, code: str) -> None:
    with SyncSessionLocal.begin() as db:
        _, submission, job, now = require_claim(db, claim)
        fail_or_retry(submission, job, now, code, retryable)


def recover_job(job_id: UUID) -> bool:
    with SyncSessionLocal.begin() as db:
        records = locked_job(db, job_id)
        if records is None:
            return False
        _, submission, job = records
        now = db.scalar(select(func.clock_timestamp()))
        if job.status == "RUNNING":
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                fail_or_retry(submission, job, now, "WORKER_LEASE_EXPIRED", True)
                return True
            return False
        if job.status not in ("PENDING", "RETRYABLE") or (
            job.next_attempt_at and job.next_attempt_at > now
        ):
            return False
        if db.scalar(
            select(OutboxEvent.id)
            .where(OutboxEvent.ai_job_id == job.id, OutboxEvent.published_at.is_(None))
            .limit(1)
        ):
            return False
        latest = db.scalar(
            select(func.max(OutboxEvent.published_at)).where(
                OutboxEvent.ai_job_id == job.id
            )
        )
        if (
            job.status == "PENDING"
            and (latest or job.created_at)
            + timedelta(seconds=settings.celery_visibility_timeout)
            > now
        ):
            return False
        db.add(
            OutboxEvent(
                ai_job_id=job.id,
                event_type="WRITING_FEEDBACK_REQUESTED",
                payload={
                    "job_id": str(job.id),
                    "practice_submission_id": str(submission.id),
                },
            )
        )
        job.status = "PENDING"
        job.stage = "WAITING_FOR_WORKER"
        job.next_attempt_at = None
        submission.evaluation_status = "PENDING"
        return True

