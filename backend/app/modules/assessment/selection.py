"""Deterministic v1 assignment: four grammar, four vocabulary, writing, speech."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.modules.assessment.blueprint import LEVELS
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.assessment.repository import AssessmentRepository
from app.modules.assessment.schemas import AssessmentItemResponse, PublicChoice
from app.modules.content.models import ContentItem

SEQUENCE = ("GRAMMAR",) * 4 + ("VOCABULARY",) * 4 + ("WRITING", "SPEAKING")


def valid_question(item: ContentItem) -> bool:
    body = item.body
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("prompt"), str)
        or not body["prompt"].strip()
    ):
        return False
    kind, skill = body.get("kind"), body.get("skill")
    if kind == "MULTIPLE_CHOICE" and skill in ("GRAMMAR", "VOCABULARY"):
        choices = body.get("choices")
        if not isinstance(choices, list) or not 2 <= len(choices) <= 6:
            return False
        if any(
            not isinstance(c, dict)
            or not isinstance(c.get("id"), str)
            or not c["id"]
            or not isinstance(c.get("text"), str)
            or not c["text"].strip()
            for c in choices
        ):
            return False
        ids = [c["id"] for c in choices]
        return (
            len(set(ids)) == len(ids)
            and body.get("correct_choice_id") in ids
            and item.cefr_level in LEVELS
        )
    return (
        (kind, skill)
        in (("SHORT_WRITING", "WRITING"), ("RECORDED_SPEAKING", "SPEAKING"))
        and isinstance(body.get("rubric"), dict)
        and bool(body["rubric"])
    )


def public_item(row: AssessmentResponse, item: ContentItem) -> AssessmentItemResponse:
    # Explicit allowlist: never serialize body, grading, rubrics or answer keys.
    body = item.body
    return AssessmentItemResponse(
        response_id=row.id,
        position=row.position,
        skill=body["skill"],
        kind=body["kind"],
        prompt=body["prompt"],
        revision=row.revision,
        optional=body["kind"] == "RECORDED_SPEAKING",
        choices=[PublicChoice(id=c["id"], text=c["text"]) for c in body["choices"]]
        if body["kind"] == "MULTIPLE_CHOICE"
        else None,
    )


class AssignmentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AssessmentRepository(session)

    async def next_item(
        self, user_id: UUID, attempt_id: UUID
    ) -> tuple[AssessmentItemResponse | None, bool]:
        # Match onboarding's user -> attempt lock order to avoid deadlocks.
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
        if attempt.status != "IN_PROGRESS":
            raise ConflictError(
                "This assessment cannot accept new questions.",
                code="ASSESSMENT_NOT_EDITABLE",
            )
        if attempt.kind != "INITIAL":
            raise ConflictError(
                "Reassessment selection is not supported.",
                code="ASSESSMENT_KIND_UNSUPPORTED",
            )
        rows = list(
            await self.session.scalars(
                select(AssessmentResponse)
                .where(
                    AssessmentResponse.assessment_attempt_id == attempt.id,
                )
                .order_by(AssessmentResponse.position)
            )
        )
        if [row.position for row in rows] != list(range(1, len(rows) + 1)) or len(
            rows
        ) > len(SEQUENCE):
            raise ConflictError(
                "Assessment assignments are inconsistent.",
                code="ASSESSMENT_STATE_INCONSISTENT",
            )
        pending = [row for row in rows if row.status == "ASSIGNED"]
        if len(pending) > 1 or (pending and pending[0] != rows[-1]):
            raise ConflictError(
                "Assessment assignments are inconsistent.",
                code="ASSESSMENT_STATE_INCONSISTENT",
            )
        # Fetch only the pinned release and share-lock published content until commit.
        bank = {
            item.id: item
            for item in await self.repository.bank(attempt.content_release)
            if valid_question(item)
        }
        for row in rows:
            item = bank.get(row.question_content_id)
            if item is None:
                raise ServiceUnavailableError(
                    "Assigned question content is unavailable.",
                    code="ASSESSMENT_CONTENT_UNAVAILABLE",
                )
            if item.body["skill"] != SEQUENCE[row.position - 1] or (
                row.status == "SKIPPED" and item.body["skill"] != "SPEAKING"
            ):
                raise ConflictError(
                    "Assessment assignments are inconsistent.",
                    code="ASSESSMENT_STATE_INCONSISTENT",
                )
        if pending:
            result = public_item(pending[0], bank[pending[0].question_content_id])
            await self.session.commit()
            return result, False
        if len(rows) == len(SEQUENCE):
            await self.session.commit()
            return None, False
        skill = SEQUENCE[len(rows)]
        target = 1  # A2 starting band, independently for grammar and vocabulary.
        history = [
            row for row in rows if bank[row.question_content_id].body["skill"] == skill
        ]
        if skill in ("GRAMMAR", "VOCABULARY") and history:
            previous = history[-1]
            correct = (
                previous.grading.get("correct")
                if isinstance(previous.grading, dict)
                else None
            )
            if type(correct) is not bool:
                raise ConflictError(
                    "The previous answer must be graded first.",
                    code="ANSWER_GRADING_REQUIRED",
                )
            target = max(
                0,
                min(
                    5,
                    LEVELS.index(bank[previous.question_content_id].cefr_level)
                    + (1 if correct else -1),
                ),
            )
        used = {row.question_content_id for row in rows}
        candidates = [
            item
            for item in bank.values()
            if item.id not in used and item.body["skill"] == skill
        ]
        if not candidates:
            raise ServiceUnavailableError(
                "No eligible question is available.",
                code="ASSESSMENT_CONTENT_UNAVAILABLE",
            )
        candidates.sort(
            key=lambda item: (
                abs(LEVELS.index(item.cefr_level) - target)
                if skill in ("GRAMMAR", "VOCABULARY")
                else 0,
                str(item.id),
            )
        )
        item = candidates[0]
        row = AssessmentResponse(
            id=uuid4(),
            assessment_attempt_id=attempt.id,
            question_content_id=item.id,
            position=len(rows) + 1,
            status="ASSIGNED",
            revision=0,
        )
        self.session.add(row)
        await self.session.commit()
        return public_item(row, item), True
