"""Bounded retention cleanup. Defaults to dry-run; use --apply to delete data."""

import argparse
import logging
from datetime import timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.infrastructure.storage.s3 import client
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.jobs.assessment_runner import locked_job
from app.modules.jobs.models import AiJob
from app.modules.media.models import MediaUpload
from app.modules.practice.models import PracticeSubmission

logger = logging.getLogger(__name__)


def live_job(attempt_id):
    return (
        select(AiJob.id)
        .where(
            AiJob.assessment_attempt_id == attempt_id,
            AiJob.status == "RUNNING",
            AiJob.lease_expires_at > func.clock_timestamp(),
        )
        .correlate_except(AiJob)
        .exists()
    )


def expired_audio():
    active_speaking = (
        select(PracticeSubmission.id)
        .join(AiJob, AiJob.practice_submission_id == PracticeSubmission.id)
        .where(
            PracticeSubmission.media_upload_id == MediaUpload.id,
            AiJob.job_type == "SPEAKING_FEEDBACK",
            AiJob.status == "RUNNING",
            AiJob.lease_expires_at > func.clock_timestamp(),
        )
        .exists()
    )
    active_audio = (
        select(AssessmentResponse.id)
        .where(
            AssessmentResponse.media_upload_id == MediaUpload.id,
            live_job(AssessmentResponse.assessment_attempt_id),
        )
        .exists()
    )
    return (
        MediaUpload.delete_after <= func.clock_timestamp(),
        MediaUpload.status != "DELETED",
        # Don't delete while a signed PUT could still recreate the object.
        (MediaUpload.upload_expires_at.is_(None))
        | (
            MediaUpload.upload_expires_at
            < func.clock_timestamp() - timedelta(minutes=15)
        ),
        ~active_audio,
        ~active_speaking,
    )


def cleanup_audio(limit: int, apply: bool) -> tuple[int, int]:
    with SyncSessionLocal() as db:
        candidates = list(
            db.execute(
                select(MediaUpload.id, MediaUpload.object_key)
                .where(*expired_audio())
                .order_by(MediaUpload.delete_after, MediaUpload.id)
                .limit(limit)
            )
        )
    removed = 0
    for upload_id, key in candidates:
        if not apply:
            continue
        try:
            # Exact persisted key, no bucket scans or prefix deletion. No DB
            # transaction is held during S3 I/O. DeleteObject is retry-safe.
            client().delete_object(Bucket=settings.s3_bucket, Key=key)
            with SyncSessionLocal.begin() as db:
                upload = db.scalar(
                    select(MediaUpload)
                    .where(
                        MediaUpload.id == upload_id,
                        MediaUpload.object_key == key,
                        *expired_audio(),
                    )
                    .with_for_update()
                )
                if upload is not None:
                    upload.status = "DELETED"
                    removed += 1
        except Exception as exc:  # noqa: BLE001 - retry failed deletions next run
            logger.warning(
                "audio_cleanup_failed upload_id=%s error_type=%s",
                upload_id,
                type(exc).__name__,
            )
    return len(candidates), removed


def cleanup_checkpoints(limit: int, apply: bool) -> tuple[int, int]:
    has_checkpoints = (
        select(AssessmentResponse.id)
        .where(
            AssessmentResponse.assessment_attempt_id == AssessmentAttempt.id,
            AssessmentResponse.grading.has_key("ai_checkpoints"),  # noqa: W601
        )
        .exists()
    )
    cutoff = func.clock_timestamp() - timedelta(
        days=settings.assessment_checkpoint_retention_days
    )
    with SyncSessionLocal() as db:
        ids = list(
            db.scalars(
                select(AiJob.id)
                .join(
                    AssessmentAttempt,
                    AssessmentAttempt.id == AiJob.assessment_attempt_id,
                )
                .where(
                    AiJob.job_type == "ASSESSMENT",
                    AiJob.user_id == AssessmentAttempt.user_id,
                    AssessmentAttempt.submitted_at <= cutoff,
                    has_checkpoints,
                    ~live_job(AssessmentAttempt.id),
                )
                .order_by(AiJob.created_at, AiJob.id)
                .limit(limit)
            )
        )
    removed = 0
    for job_id in ids:
        if not apply:
            continue
        with SyncSessionLocal.begin() as db:
            records = locked_job(db, job_id)
            if records is None:
                continue
            (
                _,
                attempt,
                _,
            ) = records
            now = db.scalar(select(func.clock_timestamp()))
            if (
                attempt.submitted_at is None
                or attempt.submitted_at
                > now - timedelta(days=settings.assessment_checkpoint_retention_days)
                or db.scalar(select(live_job(attempt.id)))
            ):
                continue
            rows = db.scalars(
                select(AssessmentResponse)
                .where(
                    AssessmentResponse.assessment_attempt_id == attempt.id,
                )
                .order_by(AssessmentResponse.position)
                .with_for_update()
            )
            for row in rows:
                if isinstance(row.grading, dict) and "ai_checkpoints" in row.grading:
                    row.grading = {
                        k: v for k, v in row.grading.items() if k != "ai_checkpoints"
                    }
                    removed += 1
    return len(ids), removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit must be between 1 and 1000")
    logging.basicConfig(level=logging.INFO)
    try:
        audio_candidates, audio_deleted = cleanup_audio(args.limit, args.apply)
        jobs, checkpoints_deleted = cleanup_checkpoints(args.limit, args.apply)
        logger.info(
            "retention apply=%s audio_candidates=%s audio_deleted=%s checkpoint_jobs=%s checkpoint_rows_deleted=%s",
            args.apply,
            audio_candidates,
            audio_deleted,
            jobs,
            checkpoints_deleted,
        )
    except Exception as exc:  # noqa: BLE001 - never log secrets or learner data
        logger.error("retention_failed error_type=%s", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
