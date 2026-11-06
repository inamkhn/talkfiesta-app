"""Fenced Vocabulary contextual sentence evaluation runner; completion credits are never modified here."""

from __future__ import annotations

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
from app.modules.practice.models import PracticeSubmission
from app.modules.vocabulary.schemas import ContextUsageFeedback

VOCAB_CONTEXT_RUBRIC_VERSION = "vocab-context-v1"
RUNNING_STAGES = {"EVALUATING_CONTEXT", "SAVING_RESULTS"}


def locked_job(db, job_id: UUID):
    identity = db.execute(
        select(AiJob.user_id, AiJob.practice_submission_id).where(
            AiJob.id == job_id, AiJob.job_type == "VOCAB_CONTEXT"
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
            PracticeSubmission.mode == "VOCAB_QUIZ",
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
    if retryable and job.attempts < settings.vocabulary_job_max_attempts:
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
            or job.attempts >= settings.vocabulary_job_max_attempts
        ):
            fail_or_retry(submission, job, now, "JOB_NOT_ELIGIBLE", False)
            return None
        job.status = "RUNNING"
        job.stage = "EVALUATING_CONTEXT"
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
    lesson = db.get(ContentItem, submission.content_item_id)
    raw_input = submission.input
    if (
        lesson is None
        or not isinstance(raw_input, dict)
        or lesson.module != "VOCABULARY"
        or lesson.kind != "VOCABULARY_LESSON"
        or lesson.status not in ("PUBLISHED", "ARCHIVED")
        or not isinstance(lesson.body, dict)
    ):
        raise ValueError("Frozen vocabulary quiz evidence is inconsistent")

    raw_answers = raw_input.get("answers")
    answers_by_item: dict[str, str] = {}
    if isinstance(raw_answers, list):
        for entry in raw_answers:
            if isinstance(entry, dict) and isinstance(entry.get("item_id"), str):
                text_val = entry.get("text")
                if isinstance(text_val, str):
                    answers_by_item[entry["item_id"]] = text_val

    exercises = lesson.body.get("exercises")
    if not isinstance(exercises, list):
        raise TypeError("Lesson exercises missing")

    context_items: list[dict[str, str]] = []
    word_ids: list[UUID] = []
    for ex in exercises:
        if not isinstance(ex, dict) or ex.get("type") != "USE_IN_CONTEXT":
            continue
        item_id = str(ex.get("item_id", "")).strip()
        raw_wid = ex.get("word_id")
        wid = raw_wid if isinstance(raw_wid, UUID) else UUID(str(raw_wid))
        word_ids.append(wid)
        context_items.append(
            {
                "item_id": item_id,
                "word_id": str(wid),
                "prompt": str(ex.get("prompt", "")),
                "sentence": answers_by_item.get(item_id, ""),
            }
        )

    if not context_items:
        raise ValueError("No USE_IN_CONTEXT exercises found for VOCAB_CONTEXT job")

    word_rows = list(
        db.scalars(
            select(ContentItem).where(
                ContentItem.id.in_(word_ids),
                ContentItem.module == "VOCABULARY",
                ContentItem.kind == "VOCAB_WORD",
            )
        )
    )
    words_by_id = {
        str(w.id): (w.body if isinstance(w.body, dict) else {}) for w in word_rows
    }
    for ctx in context_items:
        wbody = words_by_id.get(ctx["word_id"], {})
        ctx["target_word"] = str(wbody.get("word", ""))
        ctx["definition"] = str(wbody.get("definition", ""))
        ctx["part_of_speech"] = str(wbody.get("part_of_speech", ""))

    evidence = {
        "submission_id": str(submission.id),
        "target_cefr": lesson.cefr_level,
        "context_items": context_items,
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
            raise ValueError("Frozen vocabulary evidence changed between attempts")
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
    context_results: list[ContextUsageFeedback],
    trace_id: str | UUID,
) -> None:
    validated = [
        ContextUsageFeedback.model_validate(item.model_dump())
        for item in context_results
    ]
    with SyncSessionLocal.begin() as db:
        user, submission, job, now = require_claim(db, claim)
        if not user.is_active or snapshot(db, submission)[1] != fingerprint:
            raise ValueError("Frozen vocabulary evidence changed")
        if job.lease_expires_at <= db.scalar(select(func.clock_timestamp())):
            raise LostClaimError()

        existing_fb = (
            dict(submission.feedback) if isinstance(submission.feedback, dict) else {}
        )
        serialized_ctx = [item.model_dump(mode="json") for item in validated]
        existing_fb["context_result"] = serialized_ctx
        if isinstance(existing_fb.get("submit_response"), dict):
            existing_fb["submit_response"] = {
                **existing_fb["submit_response"],
                "evaluation_status": "COMPLETED",
                "context_result": serialized_ctx,
            }
        submission.feedback = existing_fb
        submission.evaluation_status = "COMPLETED"

        job.status = "SUCCEEDED"
        job.stage = "DONE"
        job.finished_at = now
        job.rubric_version = VOCAB_CONTEXT_RUBRIC_VERSION
        job.prompt_version = VOCAB_CONTEXT_RUBRIC_VERSION
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
                event_type="VOCAB_CONTEXT_REQUESTED",
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
