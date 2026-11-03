"""Read-only assessment polling with explicit public result projection."""

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.assessment.schemas import (
    AssessmentResultResponse,
    EvaluationFailure,
    EvaluationProgress,
    PublicPlacement,
    SkillPlacement,
)
from app.modules.jobs.models import AiJob

PUBLIC_STAGES = {
    "WAITING_FOR_WORKER",
    "TRANSCRIBING_AUDIO",
    "EVALUATING_LANGUAGE",
    "DETERMINING_PLACEMENT",
    "SAVING_RESULTS",
    "DONE",
}


class ResultService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID, attempt_id: UUID) -> AssessmentResultResponse:
        latest_job_id = (
            select(AiJob.id)
            .where(
                AiJob.assessment_attempt_id == AssessmentAttempt.id,
                AiJob.user_id == user_id,
                AiJob.job_type == "ASSESSMENT",
            )
            .order_by(AiJob.created_at.desc(), AiJob.id.desc())
            .limit(1)
            .correlate(AssessmentAttempt)
            .scalar_subquery()
        )
        record = (
            await self.session.execute(
                select(AssessmentAttempt, AiJob.id, AiJob.status, AiJob.stage)
                .outerjoin(AiJob, AiJob.id == latest_job_id)
                .where(
                    AssessmentAttempt.id == attempt_id,
                    AssessmentAttempt.user_id == user_id,
                )
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if record is None:
            raise NotFoundError("Assessment not found.")
        attempt, job_id, job_status, job_stage = record
        progress = self.progress(attempt.status, job_id, job_status, job_stage)
        common = {
            "assessment_id": attempt.id,
            "status": attempt.status,
            "evaluation": progress,
        }
        if attempt.status in ("SUBMITTED", "PROCESSING"):
            return AssessmentResultResponse(**common, retry_after_seconds=3)
        if attempt.status in ("FAILED_RETRYABLE", "FAILED_FINAL"):
            retryable = attempt.status == "FAILED_RETRYABLE"
            error = EvaluationFailure(
                code="EVALUATION_RETRYABLE" if retryable else "EVALUATION_FAILED",
                message="Evaluation will retry automatically."
                if retryable
                else "Evaluation failed. Please restart the assessment.",
                retryable=retryable,
            )
            progress.error = error
            return AssessmentResultResponse(
                **common,
                retry_after_seconds=5 if retryable else None,
                error=error,
            )
        if attempt.status != "COMPLETED":
            return AssessmentResultResponse(**common)
        raw = attempt.result
        if not isinstance(raw, dict):
            raise self.unavailable()
        # Never return raw JSON, job metrics, provider errors, transcripts,
        # per-answer grades, private rubrics, or traces.
        public = {
            "cefr": attempt.placement_cefr,
            "provisional": True,
            "confidence": attempt.confidence,
            **{
                key: raw.get(key)
                for key in (
                    "skills",
                    "strengths",
                    "improvement_priorities",
                    "rubric_version",
                    "assessment_version",
                )
            },
        }
        try:
            placement = PublicPlacement.model_validate(public)
        except ValidationError as exc:
            raise self.unavailable() from exc
        # Do not report speaking ability if the learner explicitly skipped it,
        # even if an evaluator accidentally produced a speaking score.
        answers = (
            await self.session.execute(
                select(AssessmentResponse.status, AssessmentResponse.answer).where(
                    AssessmentResponse.assessment_attempt_id == attempt_id,
                )
            )
        ).all()
        speaking = [
            row
            for row in answers
            if isinstance(row.answer, dict)
            and row.answer.get("kind") == "RECORDED_SPEAKING"
        ]
        if (
            len(speaking) != 1
            or speaking[0].status != "ANSWERED"
            or not speaking[0].answer.get("media_upload_id")
        ):
            reason = "NOT_ASSESSED"
            if len(speaking) == 1 and speaking[0].status == "SKIPPED":
                saved_reason = speaking[0].answer.get("skip_reason")
                if saved_reason in ("MIC_UNAVAILABLE", "DECLINED", "TECHNICAL_ISSUE"):
                    reason = saved_reason
            placement.skills.speaking = SkillPlacement(
                level=None, assessed=False, reason=reason
            )
            placement.confidence = "LOW"
        return AssessmentResultResponse(**common, placement=placement)

    @staticmethod
    def progress(
        attempt_status: str,
        job_id: UUID | None,
        job_status: str | None,
        job_stage: str | None,
    ) -> EvaluationProgress:
        mapping = {
            "IN_PROGRESS": (None, "NOT_STARTED"),
            "SUBMITTED": ("PENDING", "QUEUED"),
            "PROCESSING": ("RUNNING", "RUNNING"),
            "FAILED_RETRYABLE": ("RETRYABLE", "RETRY_SCHEDULED"),
            "FAILED_FINAL": ("FAILED", "FAILED_FINAL"),
            "COMPLETED": ("SUCCEEDED", "SUCCEEDED"),
        }
        expected, status = mapping[attempt_status]
        # Historical terminal attempts may predate durable jobs. Active submitted
        # attempts must have a consistent job; don't fabricate worker progress.
        if job_status != expected and not (
            job_id is None and attempt_status in ("COMPLETED", "FAILED_FINAL")
        ):
            raise ServiceUnavailableError(
                "Assessment progress is temporarily unavailable. Please try again later.",
                code="ASSESSMENT_PROGRESS_UNAVAILABLE",
            )
        if status == "NOT_STARTED":
            stage = None
        elif status == "QUEUED":
            stage = "WAITING_FOR_WORKER"
        elif status == "SUCCEEDED":
            stage = "DONE"
        else:
            stage = job_stage if job_stage in PUBLIC_STAGES - {"DONE"} else None
        return EvaluationProgress(job_id=job_id, status=status, stage=stage)

    @staticmethod
    def unavailable() -> ServiceUnavailableError:
        return ServiceUnavailableError(
            "The saved assessment result is incomplete. Please try again later.",
            code="ASSESSMENT_RESULT_UNAVAILABLE",
        )
