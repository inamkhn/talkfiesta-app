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
    PublicPlacement,
    SkillPlacement,
)


class ResultService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: UUID, attempt_id: UUID) -> AssessmentResultResponse:
        attempt = await self.session.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.user_id == user_id,
            )
        )
        if attempt is None:
            raise NotFoundError("Assessment not found.")
        if attempt.status in ("SUBMITTED", "PROCESSING"):
            return AssessmentResultResponse(
                status=attempt.status, retry_after_seconds=3
            )
        if attempt.status in ("FAILED_RETRYABLE", "FAILED_FINAL"):
            retryable = attempt.status == "FAILED_RETRYABLE"
            return AssessmentResultResponse(
                status=attempt.status,
                retry_after_seconds=5 if retryable else None,
                error=EvaluationFailure(
                    code="EVALUATION_RETRYABLE" if retryable else "EVALUATION_FAILED",
                    message="Evaluation could not finish and is eligible for retry."
                    if retryable
                    else "Evaluation failed. Please restart the assessment.",
                    retryable=retryable,
                ),
            )
        if attempt.status != "COMPLETED":
            return AssessmentResultResponse(status=attempt.status)
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
                )
            },
        }
        try:
            placement = PublicPlacement.model_validate(public)
        except ValidationError as exc:
            raise self.unavailable() from exc
        # Do not report speaking ability if the learner explicitly skipped it,
        # even if an evaluator accidentally produced a speaking score.
        answers = list(
            await self.session.scalars(
                select(AssessmentResponse).where(
                    AssessmentResponse.assessment_attempt_id == attempt_id,
                )
            )
        )
        speaking = [
            row
            for row in answers
            if isinstance(row.answer, dict)
            and row.answer.get("kind") == "RECORDED_SPEAKING"
        ]
        if (
            len(speaking) != 1
            or speaking[0].status != "ANSWERED"
            or speaking[0].media_upload_id is None
        ):
            reason = "NOT_ASSESSED"
            if len(speaking) == 1 and speaking[0].status == "SKIPPED":
                saved_reason = speaking[0].answer.get("skip_reason")
                if saved_reason in ("MIC_UNAVAILABLE", "DECLINED", "TECHNICAL_ISSUE"):
                    reason = saved_reason
            placement.skills.speaking = SkillPlacement(
                level=None, assessed=False, reason=reason
            )
        return AssessmentResultResponse(status="COMPLETED", placement=placement)

    @staticmethod
    def unavailable() -> ServiceUnavailableError:
        return ServiceUnavailableError(
            "The saved assessment result is incomplete. Please try again later.",
            code="ASSESSMENT_RESULT_UNAVAILABLE",
        )
