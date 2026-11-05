"""Owner-scoped polling from one consistent PostgreSQL statement snapshot."""

import logging
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.modules.jobs.models import AiJob
from app.modules.learning.models import ActivityCompletion
from app.modules.practice.models import PracticeSubmission
from app.modules.speaking.feedback import SpeakingFeedback
from app.modules.speaking.schemas import (
    SpeakingEvaluationError,
    SpeakingEvaluationProgress,
    SpeakingSubmissionDetail,
)

logger = logging.getLogger(__name__)
RUNNING_STAGES = {"TRANSCRIBING_AUDIO", "EVALUATING_LANGUAGE", "SAVING_RESULTS"}


def submission_detail_statement(user_id: UUID, submission_id: UUID):
    latest_job = (
        select(AiJob.id)
        .where(
            AiJob.practice_submission_id == PracticeSubmission.id,
            AiJob.user_id == user_id,
            AiJob.job_type == "SPEAKING_FEEDBACK",
        )
        .order_by(AiJob.created_at.desc(), AiJob.id.desc())
        .limit(1)
        .correlate(PracticeSubmission)
        .scalar_subquery()
    )
    credited = (
        select(ActivityCompletion.id)
        .where(
            ActivityCompletion.user_id == user_id,
            ActivityCompletion.source_submission_id == PracticeSubmission.id,
            ActivityCompletion.module_progress_id
            == PracticeSubmission.module_progress_id,
            ActivityCompletion.content_item_id == PracticeSubmission.content_item_id,
        )
        .correlate(PracticeSubmission)
        .exists()
    )
    return (
        select(
            PracticeSubmission.id,
            PracticeSubmission.content_item_id,
            PracticeSubmission.status,
            PracticeSubmission.evaluation_status,
            PracticeSubmission.transcript,
            PracticeSubmission.feedback,
            AiJob.id.label("job_id"),
            AiJob.status.label("job_status"),
            AiJob.stage,
            AiJob.rubric_version,
            credited.label("credited"),
        )
        .outerjoin(AiJob, AiJob.id == latest_job)
        .where(
            PracticeSubmission.id == submission_id,
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.mode == "RECORDED_SPEAKING",
        )
    )


class SpeakingResultService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID, submission_id: UUID) -> SpeakingSubmissionDetail:
        row = (
            await self.session.execute(
                submission_detail_statement(user_id, submission_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("Speaking submission not found.")
        try:
            common = {"submission_id": row.id, "content_item_id": row.content_item_id}
            if row.status in ("DRAFT", "REJECTED"):
                if (
                    row.credited
                    or row.job_id is not None
                    or row.evaluation_status != "NOT_REQUIRED"
                ):
                    raise ValueError("Unexpected draft evaluation state")
                return SpeakingSubmissionDetail(
                    **common,
                    activity_status="IN_PROGRESS"
                    if row.status == "DRAFT"
                    else "REJECTED",
                    evaluation=SpeakingEvaluationProgress(
                        status="NOT_REQUIRED", stage="NOT_STARTED"
                    ),
                )
            if row.status != "ACCEPTED" or not row.credited or row.job_id is None:
                raise ValueError("Acceptance, credit or job missing")
            expected = {
                "PENDING": "PENDING",
                "RETRYABLE": "PENDING",
                "RUNNING": "PROCESSING",
                "SUCCEEDED": "COMPLETED",
                "FAILED": "FAILED",
            }
            if (
                row.job_status not in expected
                or row.evaluation_status != expected[row.job_status]
            ):
                raise ValueError("Evaluation state disagrees with job")
            transcript = None
            feedback = None
            if row.job_status in ("PENDING", "RETRYABLE"):
                retrying = row.job_status == "RETRYABLE"
                evaluation = SpeakingEvaluationProgress(
                    status="PENDING",
                    stage="RETRY_SCHEDULED" if retrying else "WAITING_FOR_WORKER",
                    retry_after_seconds=5 if retrying else 3,
                )
            elif row.job_status == "RUNNING":
                if row.stage not in RUNNING_STAGES:
                    raise ValueError("Unknown running stage")
                evaluation = SpeakingEvaluationProgress(
                    status="PROCESSING",
                    stage=row.stage,
                    retry_after_seconds=3,
                )
            elif row.job_status == "FAILED":
                evaluation = SpeakingEvaluationProgress(
                    status="FAILED", stage="FAILED", error=SpeakingEvaluationError()
                )
                transcript = row.transcript
            else:
                if (
                    row.transcript is None
                    or not row.rubric_version
                    or not isinstance(row.feedback, dict)
                ):
                    raise ValueError("Completed evaluation is incomplete")
                feedback = SpeakingFeedback.model_validate(row.feedback)
                if any(c.original not in row.transcript for c in feedback.corrections):
                    raise ValueError("Correction is not grounded in transcript")
                if feedback.reviewable and not row.transcript.strip():
                    raise ValueError("Empty transcript cannot have scores")
                transcript = row.transcript
                evaluation = SpeakingEvaluationProgress(
                    status="COMPLETED", stage="DONE", rubric_version=row.rubric_version
                )
            return SpeakingSubmissionDetail(
                **common,
                activity_status="COMPLETED",
                evaluation=evaluation,
                transcript=transcript,
                feedback=feedback,
            )
        except (ValueError, ValidationError, TypeError):
            logger.error("speaking_result_inconsistent submission_id=%s", submission_id)
            raise ServiceUnavailableError(
                "Speaking feedback is temporarily unavailable.",
                code="SPEAKING_RESULT_UNAVAILABLE",
            ) from None
