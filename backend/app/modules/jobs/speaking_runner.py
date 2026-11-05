"""Fenced Speaking execution; completion credits are never modified here."""

import hashlib
import json
import random
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.core.config import settings
from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.jobs.assessment_runner import JobClaim, LostClaimError
from app.modules.jobs.models import AiJob, OutboxEvent
from app.modules.learning.models import ActivityCompletion
from app.modules.media.models import MediaUpload
from app.modules.practice.models import PracticeSubmission


def locked_job(db, job_id):
    identity = db.execute(
        select(AiJob.user_id, AiJob.practice_submission_id).where(
            AiJob.id == job_id, AiJob.job_type == "SPEAKING_FEEDBACK"
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
            PracticeSubmission.mode == "RECORDED_SPEAKING",
        )
        .with_for_update()
    )
    job = db.scalar(select(AiJob).where(AiJob.id == job_id).with_for_update())
    if user is None or submission is None or job is None:
        return None
    return user, submission, job


def fail_or_retry(submission, job, now, code, retryable):
    job.claim_token = None
    job.lease_expires_at = None
    job.last_error_code = code
    if retryable and job.attempts < settings.speaking_job_max_attempts:
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


def claim_job(job_id: UUID):
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
            or job.attempts >= settings.speaking_job_max_attempts
        ):
            fail_or_retry(submission, job, now, "JOB_NOT_ELIGIBLE", False)
            return None
        job.status = "RUNNING"
        job.stage = "TRANSCRIBING_AUDIO"
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


def require_claim(db, claim):
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


def snapshot(db, submission):
    item = db.get(ContentItem, submission.content_item_id)
    upload = db.get(MediaUpload, submission.media_upload_id)
    credit = db.scalar(
        select(ActivityCompletion).where(
            ActivityCompletion.source_submission_id == submission.id,
            ActivityCompletion.user_id == submission.user_id,
            ActivityCompletion.module_progress_id == submission.module_progress_id,
            ActivityCompletion.content_item_id == submission.content_item_id,
        )
    )
    saved = submission.input
    if (
        item is None
        or upload is None
        or credit is None
        or not isinstance(saved, dict)
        or item.kind != "SPEAKING_LESSON"
        or item.module != "SPEAKING"
        or item.slot != "CORE"
        or saved.get("day") != item.day
        or saved.get("target_cefr") != item.cefr_level
        or item.status not in ("PUBLISHED", "ARCHIVED")
        or saved.get("content_version") != item.content_version
        or saved.get("content_release") != item.release_key
        or saved.get("content_item_id") != str(item.id)
        or saved.get("media_upload_id") != str(upload.id)
        or upload.user_id != submission.user_id
        or upload.purpose != "SPEAKING"
        or upload.verified_at is None
        or upload.content_type != "audio/webm"
        or saved.get("checksum_sha256") != upload.checksum_sha256
        or saved.get("size_bytes") != upload.size_bytes
        or saved.get("duration_seconds") != str(upload.duration_seconds)
        or upload.duration_seconds is None
        or not upload.duration_seconds.is_finite()
        or upload.duration_seconds <= 0
        or not isinstance(item.body, dict)
    ):
        raise ValueError("Frozen speaking evidence is inconsistent")
    evidence = {
        "submission_id": str(submission.id),
        "input": saved,
        "instructions": item.body.get("instructions"),
        "topic": item.body.get("topic"),
        "exercise_type": item.body.get("exercise_type"),
        "object_key": upload.object_key,
        "content_type": upload.content_type,
        "size_bytes": upload.size_bytes,
        "checksum": upload.checksum_sha256,
        "duration": str(upload.duration_seconds),
    }
    if (
        not isinstance(evidence["instructions"], str)
        or not evidence["instructions"].strip()
    ):
        raise ValueError("Speaking instructions missing")
    fingerprint = hashlib.sha256(
        json.dumps(evidence, sort_keys=True).encode()
    ).hexdigest()
    return evidence, fingerprint, upload


def load_evidence(claim):
    with SyncSessionLocal.begin() as db:
        user, submission, job, now = require_claim(db, claim)
        if not user.is_active:
            raise ValueError("Account inactive")
        evidence, fingerprint, upload = snapshot(db, submission)
        metrics = job.metrics or {}
        if metrics.get("evidence_fingerprint", fingerprint) != fingerprint:
            raise ValueError("Frozen evidence changed between attempts")
        if (
            submission.transcript is not None
            and metrics.get("transcript_hash")
            != hashlib.sha256(submission.transcript.encode()).hexdigest()
        ):
            raise ValueError("Original transcript changed")
        job.metrics = {**metrics, "evidence_fingerprint": fingerprint}
        if submission.transcript is None and (
            upload.status != "VERIFIED"
            or upload.delete_after is None
            or upload.delete_after <= now
        ):
            raise ValueError("Recording no longer available")
        return evidence, fingerprint, submission.transcript


def report_stage(claim, stage):
    if stage not in ("TRANSCRIBING_AUDIO", "EVALUATING_LANGUAGE", "SAVING_RESULTS"):
        raise ValueError("Unknown stage")
    with SyncSessionLocal.begin() as db:
        _, _, job, _ = require_claim(db, claim)
        job.stage = stage


def save_transcript(claim, fingerprint, transcript):
    if not isinstance(transcript, str) or len(transcript) > 20000:
        raise ValueError("Invalid transcript")
    with SyncSessionLocal.begin() as db:
        user, submission, job, _ = require_claim(db, claim)
        if not user.is_active or snapshot(db, submission)[1] != fingerprint:
            raise ValueError("Frozen evidence changed")
        if submission.transcript is not None and submission.transcript != transcript:
            raise ValueError("Original transcript is immutable")
        if job.lease_expires_at <= db.scalar(select(func.clock_timestamp())):
            raise LostClaimError()
        submission.transcript = transcript
        job.metrics = {
            **(job.metrics or {}),
            "transcript_hash": hashlib.sha256(transcript.encode()).hexdigest(),
        }


def finish(claim, fingerprint, feedback, trace_id):
    from app.modules.speaking.feedback import RUBRIC_VERSION, SpeakingFeedback

    feedback = SpeakingFeedback.model_validate(feedback.model_dump())
    with SyncSessionLocal.begin() as db:
        user, submission, job, now = require_claim(db, claim)
        if (
            not user.is_active
            or snapshot(db, submission)[1] != fingerprint
            or submission.transcript is None
            or (job.metrics or {}).get("transcript_hash")
            != hashlib.sha256(submission.transcript.encode()).hexdigest()
        ):
            raise ValueError("Frozen evidence changed")
        if any(c.original not in submission.transcript for c in feedback.corrections):
            raise ValueError("Corrections must quote the original transcript")
        if job.lease_expires_at <= db.scalar(select(func.clock_timestamp())):
            raise LostClaimError()
        submission.feedback = feedback.model_dump(mode="json")
        submission.evaluation_status = "COMPLETED"
        job.status = "SUCCEEDED"
        job.stage = "DONE"
        job.finished_at = now
        job.rubric_version = RUBRIC_VERSION
        job.prompt_version = RUBRIC_VERSION
        job.model = settings.openai_evaluation_model
        job.langsmith_run_id = str(trace_id)
        job.claim_token = None
        job.lease_expires_at = None


def fail(claim, retryable, code):
    with SyncSessionLocal.begin() as db:
        _, submission, job, now = require_claim(db, claim)
        fail_or_retry(submission, job, now, code, retryable)


def recover_job(job_id):
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
                event_type="SPEAKING_FEEDBACK_REQUESTED",
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
