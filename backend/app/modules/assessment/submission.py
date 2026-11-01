"""Freeze validated answers and enqueue evaluation in one database transaction."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.modules.assessment.models import (
    AssessmentAttempt,
    AssessmentResponse,
    AssessmentSubmitRequest,
)
from app.modules.assessment.repository import AssessmentRepository
from app.modules.assessment.schemas import (
    ChoiceAnswer,
    SaveAnswerRequest,
    SpeakingAnswer,
    SubmitAssessmentResponse,
    WritingAnswer,
)
from app.modules.assessment.selection import SEQUENCE, valid_question
from app.modules.jobs.models import AiJob, OutboxEvent
from app.modules.media.models import MediaUpload

ANSWER_ADAPTER = TypeAdapter(SaveAnswerRequest)


def incomplete(detail: str) -> ConflictError:
    return ConflictError(detail, code="ASSESSMENT_INCOMPLETE")


class SubmissionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AssessmentRepository(session)

    async def submit(
        self, user_id: UUID, attempt_id: UUID, key: str
    ) -> SubmitAssessmentResponse:
        user = await self.repository.lock_user(user_id)
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")
        attempt = await self.session.scalar(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.user_id == user_id,
            )
            .with_for_update()
        )
        if attempt is None:
            raise NotFoundError("Assessment not found.")
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        prior = await self.session.get(AssessmentSubmitRequest, (user_id, key_hash))
        if prior is not None and prior.assessment_attempt_id != attempt_id:
            raise ConflictError(
                "This submission key belongs to another assessment.",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        job_key = f"assessment:{attempt_id}:evaluation:v1"
        job = await self.session.scalar(
            select(AiJob).where(AiJob.idempotency_key == job_key)
        )
        if job is not None:
            if (
                job.user_id != user_id
                or job.assessment_attempt_id != attempt_id
                or job.job_type != "ASSESSMENT"
                or attempt.status == "IN_PROGRESS"
            ):
                raise ConflictError(
                    "The saved evaluation state is inconsistent.",
                    code="ASSESSMENT_STATE_INCONSISTENT",
                )
            # New keys for the same assessment also resolve to the original job.
            if prior is None:
                self.remember(user_id, key_hash, attempt_id)
                await self.session.commit()
            return self.result(attempt, job)
        if prior is not None or attempt.status != "IN_PROGRESS":
            raise ConflictError(
                "This assessment cannot be submitted in its current state.",
                code="ASSESSMENT_NOT_SUBMITTABLE",
            )
        if attempt.kind != "INITIAL":
            raise ConflictError(
                "Reassessment is not supported yet.", code="ASSESSMENT_KIND_UNSUPPORTED"
            )
        await self.validate_answers(attempt)
        attempt.status = "SUBMITTED"
        attempt.submitted_at = datetime.now(UTC)
        job = AiJob(
            id=uuid4(),
            user_id=user_id,
            job_type="ASSESSMENT",
            assessment_attempt_id=attempt_id,
            status="PENDING",
            idempotency_key=job_key,
        )
        self.session.add(job)
        await self.session.flush()
        self.session.add(
            OutboxEvent(
                ai_job_id=job.id,
                event_type="EVALUATION_REQUESTED",
                payload={
                    "job_id": str(job.id),
                    "assessment_attempt_id": str(attempt_id),
                },
            )
        )
        self.remember(user_id, key_hash, attempt_id)
        await self.session.commit()
        return self.result(attempt, job)

    def remember(self, user_id: UUID, key_hash: str, attempt_id: UUID) -> None:
        self.session.add(
            AssessmentSubmitRequest(
                user_id=user_id, key_hash=key_hash, assessment_attempt_id=attempt_id
            )
        )

    async def validate_answers(self, attempt: AssessmentAttempt) -> None:
        rows = list(
            await self.session.scalars(
                select(AssessmentResponse)
                .where(
                    AssessmentResponse.assessment_attempt_id == attempt.id,
                )
                .order_by(AssessmentResponse.position)
                .with_for_update()
            )
        )
        if len(rows) != len(SEQUENCE) or [row.position for row in rows] != list(
            range(1, len(SEQUENCE) + 1)
        ):
            raise incomplete(
                "Complete all assigned assessment items before submitting."
            )
        bank = {
            item.id: item
            for item in await self.repository.bank(attempt.content_release)
        }
        for row, skill in zip(rows, SEQUENCE, strict=True):
            if row.status not in ("ANSWERED", "SKIPPED") or row.answered_at is None:
                raise incomplete(
                    "Finalize every answer; writing drafts cannot be submitted."
                )
            item = bank.get(row.question_content_id)
            if item is None or not valid_question(item) or item.body["skill"] != skill:
                raise incomplete(
                    "Assigned assessment content is unavailable or inconsistent."
                )
            if not isinstance(row.answer, dict):
                raise incomplete("An assigned answer is missing.")
            try:
                answer = ANSWER_ADAPTER.validate_python(
                    {**row.answer, "expected_revision": row.revision}
                )
            except ValidationError as exc:
                raise incomplete(
                    "A stored answer is invalid. Review the assessment."
                ) from exc
            if answer.kind != item.body["kind"]:
                raise incomplete("An answer does not match its assigned question.")
            if isinstance(answer, ChoiceAnswer):
                choices = {choice["id"] for choice in item.body["choices"]}
                correct = (
                    row.grading.get("correct")
                    if isinstance(row.grading, dict)
                    else None
                )
                if (
                    row.status != "ANSWERED"
                    or answer.selected_choice_id not in choices
                    or type(correct) is not bool
                    or correct
                    != (answer.selected_choice_id == item.body["correct_choice_id"])
                ):
                    raise incomplete(
                        "An objective answer is not finalized and consistently graded."
                    )
            elif isinstance(answer, WritingAnswer):
                if row.status != "ANSWERED" or not answer.finalize:
                    raise incomplete("Finalize the writing answer before submitting.")
            elif isinstance(answer, SpeakingAnswer):
                if answer.skipped:
                    if row.status != "SKIPPED" or row.media_upload_id is not None:
                        raise incomplete("The speaking skip is inconsistent.")
                else:
                    if (
                        row.status != "ANSWERED"
                        or row.media_upload_id != answer.media_upload_id
                    ):
                        raise incomplete(
                            "The speaking audio is not bound to this response."
                        )
                    await self.validate_audio(attempt.user_id, answer.media_upload_id)
            if (
                not isinstance(answer, SpeakingAnswer)
                and row.media_upload_id is not None
            ):
                raise incomplete("Unexpected audio attached to a non-speaking answer.")

    async def validate_audio(self, user_id: UUID, media_id: UUID) -> None:
        upload = await self.session.scalar(
            select(MediaUpload)
            .where(
                MediaUpload.id == media_id,
                MediaUpload.user_id == user_id,
            )
            .with_for_update()
        )
        if upload is None:
            raise ConflictError(
                "The speaking upload is unavailable.",
                code="ASSESSMENT_AUDIO_UNAVAILABLE",
            )
        expiry = upload.delete_after
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if (
            upload.status != "VERIFIED"
            or upload.purpose != "ASSESSMENT"
            or upload.verified_at is None
            or (expiry is not None and expiry <= datetime.now(UTC))
        ):
            raise ConflictError(
                "The speaking upload must be verified and available.",
                code="ASSESSMENT_AUDIO_UNAVAILABLE",
            )

    @staticmethod
    def result(attempt: AssessmentAttempt, job: AiJob) -> SubmitAssessmentResponse:
        return SubmitAssessmentResponse(
            attempt_id=attempt.id,
            status=attempt.status,
            job_id=job.id,
            result_url=f"/api/v1/assessments/{attempt.id}/result",
        )
