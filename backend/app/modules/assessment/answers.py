"""Versioned answer saves; finalized answers cannot alter adaptive history."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationAppError,
)
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.assessment.repository import AssessmentRepository
from app.modules.assessment.schemas import (
    ChoiceAnswer,
    SaveAnswerRequest,
    SaveAnswerResponse,
    SpeakingAnswer,
    WritingAnswer,
)
from app.modules.assessment.selection import valid_question
from app.modules.content.models import ContentItem
from app.modules.media.models import MediaUpload


class AnswerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self,
        user_id: UUID,
        attempt_id: UUID,
        response_id: UUID,
        payload: SaveAnswerRequest,
    ) -> SaveAnswerResponse:
        user = await AssessmentRepository(self.session).lock_user(user_id)
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
        if attempt.status != "IN_PROGRESS":
            raise ConflictError(
                "Submitted assessments cannot be edited.",
                code="ASSESSMENT_NOT_EDITABLE",
            )
        row = await self.session.scalar(
            select(AssessmentResponse)
            .where(
                AssessmentResponse.id == response_id,
                AssessmentResponse.assessment_attempt_id == attempt_id,
            )
            .with_for_update()
        )
        if row is None:
            raise NotFoundError("Assigned response not found.")
        answer = payload.model_dump(mode="json", exclude={"expected_revision"})
        # Only the immediately preceding identical write is a safe retry. Older
        # requests cannot overwrite intervening edits even if their text matches.
        if payload.expected_revision != row.revision:
            if payload.expected_revision == row.revision - 1 and row.answer == answer:
                return self.result(row)
            raise ConflictError(
                "The answer has changed. Reload its current revision.",
                code="VERSION_CONFLICT",
            )
        if row.status != "ASSIGNED":
            raise ConflictError(
                "This answer has already been finalized.", code="ANSWER_FINALIZED"
            )
        item = await self.session.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == row.question_content_id,
                ContentItem.release_key == attempt.content_release,
                ContentItem.status == "PUBLISHED",
                ContentItem.kind == "ASSESSMENT_QUESTION",
            )
            .with_for_update(read=True)
        )
        if item is None or not valid_question(item):
            raise ServiceUnavailableError(
                "Assigned question content is unavailable.",
                code="ASSESSMENT_CONTENT_UNAVAILABLE",
            )
        if item.body["kind"] != payload.kind:
            raise ValidationAppError(
                "The answer kind does not match the assigned question."
            )
        grading = None
        status = "ANSWERED"
        media_id = None
        if isinstance(payload, ChoiceAnswer):
            if payload.selected_choice_id not in {
                c["id"] for c in item.body["choices"]
            }:
                raise ValidationAppError("Choose an option from the assigned question.")
            grading = {
                "correct": payload.selected_choice_id == item.body["correct_choice_id"]
            }
        elif isinstance(payload, WritingAnswer):
            status = "ANSWERED" if payload.finalize else "ASSIGNED"
        elif isinstance(payload, SpeakingAnswer):
            if payload.skipped:
                status = "SKIPPED"
            else:
                upload = await self.session.scalar(
                    select(MediaUpload)
                    .where(
                        MediaUpload.id == payload.media_upload_id,
                        MediaUpload.user_id == user_id,
                    )
                    .with_for_update()
                )
                if upload is None:
                    raise NotFoundError("Audio upload not found.")
                # Confirmation must bind this response to the upload. Ownership
                # alone must not allow arbitrary old recordings to be attached.
                if row.media_upload_id != upload.id:
                    raise ValidationAppError(
                        "The upload is not bound to this assessment response."
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
                    raise ValidationAppError(
                        "The assessment audio must be verified and available."
                    )
                media_id = upload.id
        row.answer = answer
        row.grading = grading
        row.media_upload_id = media_id
        row.status = status
        row.revision += 1
        row.answered_at = datetime.now(UTC) if status != "ASSIGNED" else None
        await self.session.commit()
        return self.result(row)

    @staticmethod
    def result(row: AssessmentResponse) -> SaveAnswerResponse:
        return SaveAnswerResponse(
            response_id=row.id, status=row.status, revision=row.revision
        )
