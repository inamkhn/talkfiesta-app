"""Create, resume, read, autosave, and submit daily vocabulary quiz sessions."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationAppError,
)
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.jobs.models import AiJob, OutboxEvent
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.practice.models import PracticeSubmission
from app.modules.vocabulary.models import UserVocabulary
from app.modules.vocabulary.repository import VocabularyRepository
from app.modules.vocabulary.schemas import (
    ContextUsageFeedback,
    FillBlankQuestion,
    MatchChoiceOption,
    MatchDefinitionQuestion,
    ObjectiveQuizResult,
    SaveVocabPracticeAnswersRequest,
    SaveVocabPracticeAnswersResponse,
    SubmitVocabPracticeRequest,
    SubmitVocabPracticeResponse,
    SubmitVocabReviewAnswer,
    SubmitVocabReviewRequest,
    SubmitVocabReviewResponse,
    UseInContextQuestion,
    VocabPracticeSessionResponse,
    VocabQuizQuestion,
)
from app.modules.vocabulary.service import (
    TARGET_DAILY_WORD_COUNT,
    VocabularyQueryService,
    _parse_word_ids,
)
from app.modules.vocabulary.srs import apply_review_outcome, initial_word_schedule

logger = logging.getLogger(__name__)


def project_public_questions(item: ContentItem) -> list[VocabQuizQuestion]:
    """Validate published exercises and strip private answer keys before returning."""
    body = item.body if isinstance(item.body, dict) else {}
    word_ids = set(_parse_word_ids(body.get("word_content_ids")))
    raw_exercises = body.get("exercises")
    if not isinstance(raw_exercises, list) or not 1 <= len(raw_exercises) <= 30:
        raise ValueError("Vocabulary lesson must contain 1 to 30 exercises.")

    questions: list[VocabQuizQuestion] = []
    seen_ids: set[str] = set()

    for raw in raw_exercises:
        if not isinstance(raw, dict):
            raise TypeError("Exercise entry must be an object.")
        item_id = raw.get("item_id")
        ex_type = raw.get("type")
        prompt = raw.get("prompt")
        if (
            not isinstance(item_id, str)
            or not item_id.strip()
            or item_id in seen_ids
            or not isinstance(prompt, str)
            or not prompt.strip()
        ):
            raise ValueError("Exercise has invalid or duplicate item_id/prompt.")
        seen_ids.add(item_id)

        if ex_type == "FILL_BLANK":
            choices = raw.get("choices")
            correct = raw.get("correct_choice") or raw.get("correct_answer")
            if (
                not isinstance(choices, list)
                or not 2 <= len(choices) <= 6
                or any(not isinstance(c, str) or not c.strip() for c in choices)
                or len(set(choices)) != len(choices)
                or correct not in choices
            ):
                raise ValueError("Invalid FILL_BLANK choices or answer key.")
            questions.append(
                FillBlankQuestion(
                    item_id=item_id,
                    prompt=prompt,
                    choices=choices,
                )
            )
        elif ex_type == "MATCH_DEFINITION":
            choices = raw.get("choices")
            correct_id = raw.get("correct_choice_id")
            if not isinstance(choices, list) or not 2 <= len(choices) <= 6:
                raise ValueError("Invalid MATCH_DEFINITION choices.")
            option_list: list[MatchChoiceOption] = []
            option_ids: list[str] = []
            for c in choices:
                if not isinstance(c, dict):
                    raise TypeError("MATCH_DEFINITION choice must be an object.")
                opt = MatchChoiceOption(id=c.get("id", ""), text=c.get("text", ""))
                option_list.append(opt)
                option_ids.append(opt.id)
            if len(set(option_ids)) != len(option_ids) or correct_id not in option_ids:
                raise ValueError("Invalid MATCH_DEFINITION answer key.")
            questions.append(
                MatchDefinitionQuestion(
                    item_id=item_id,
                    prompt=prompt,
                    choices=option_list,
                )
            )
        elif ex_type == "USE_IN_CONTEXT":
            raw_word_id = raw.get("word_id")
            word_uuid = (
                raw_word_id
                if isinstance(raw_word_id, UUID)
                else UUID(str(raw_word_id))
            )
            if word_uuid not in word_ids:
                raise ValueError("USE_IN_CONTEXT word_id must belong to this lesson.")
            questions.append(
                UseInContextQuestion(
                    item_id=item_id,
                    word_id=word_uuid,
                    prompt=prompt,
                )
            )
        else:
            raise ValueError(f"Unsupported vocabulary exercise type: {ex_type}")

    return questions


def grade_objective_exercises(
    item: ContentItem,
    saved_answers: dict[str, str],
) -> tuple[ObjectiveQuizResult, list[dict[str, object]], bool]:
    """Grade objective exercises and return (ObjectiveQuizResult, item_grades, has_context)."""
    raw_exercises = item.body.get("exercises", [])
    correct_count = 0
    total_objective = 0
    has_context = False
    graded_items: list[dict[str, object]] = []

    for raw in raw_exercises:
        item_id = raw["item_id"]
        ex_type = raw["type"]
        user_val = saved_answers.get(item_id, "").strip()
        if not user_val:
            raise ValidationAppError(
                f"Answer for question '{item_id}' is required before submitting.",
                code="INCOMPLETE_QUIZ_ANSWERS",
            )
        if ex_type == "FILL_BLANK":
            total_objective += 1
            expected = raw.get("correct_choice") or raw.get("correct_answer")
            is_correct = user_val == expected
            if is_correct:
                correct_count += 1
            graded_items.append(
                {"item_id": item_id, "type": ex_type, "correct": is_correct}
            )
        elif ex_type == "MATCH_DEFINITION":
            total_objective += 1
            expected = raw.get("correct_choice_id")
            is_correct = user_val == expected
            if is_correct:
                correct_count += 1
            graded_items.append(
                {"item_id": item_id, "type": ex_type, "correct": is_correct}
            )
        elif ex_type == "USE_IN_CONTEXT":
            has_context = True
            graded_items.append(
                {
                    "item_id": item_id,
                    "type": ex_type,
                    "word_id": str(raw["word_id"]),
                    "text": user_val,
                }
            )

    return (
        ObjectiveQuizResult(correct=correct_count, total=total_objective),
        graded_items,
        has_context,
    )


def extract_saved_answers(raw_input: object) -> dict[str, str]:
    if not isinstance(raw_input, dict):
        return {}
    answers = raw_input.get("answers")
    if isinstance(answers, dict):
        return {
            str(k): str(v)
            for k, v in answers.items()
            if isinstance(k, str) and isinstance(v, str)
        }
    if isinstance(answers, list):
        mapped: dict[str, str] = {}
        for entry in answers:
            if not isinstance(entry, dict):
                continue
            item_id = entry.get("item_id")
            value = (
                entry.get("choice_id")
                if entry.get("choice_id") is not None
                else entry.get("text")
            )
            if isinstance(item_id, str) and isinstance(value, str):
                mapped[item_id] = value
        return mapped
    return {}


def _validate_and_merge_answers(
    questions: list[VocabQuizQuestion],
    existing_answers: dict[str, str],
    payload: SaveVocabPracticeAnswersRequest,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    by_id = {q.item_id: q for q in questions}
    seen_in_payload: set[str] = set()
    merged = dict(existing_answers)

    for ans in payload.answers:
        if ans.item_id in seen_in_payload:
            raise ValidationAppError(
                "Duplicate item_id in answers.",
                code="INVALID_QUIZ_ITEM",
            )
        seen_in_payload.add(ans.item_id)
        question = by_id.get(ans.item_id)
        if question is None:
            raise ValidationAppError(
                f"Question '{ans.item_id}' is not part of this vocabulary quiz.",
                code="INVALID_QUIZ_ITEM",
            )
        if isinstance(question, FillBlankQuestion):
            if ans.choice_id is None or ans.choice_id not in question.choices:
                raise ValidationAppError(
                    f"Invalid choice for question '{ans.item_id}'.",
                    code="INVALID_QUIZ_ITEM",
                )
            merged[ans.item_id] = ans.choice_id
        elif isinstance(question, MatchDefinitionQuestion):
            valid_ids = {opt.id for opt in question.choices}
            if ans.choice_id is None or ans.choice_id not in valid_ids:
                raise ValidationAppError(
                    f"Invalid choice for question '{ans.item_id}'.",
                    code="INVALID_QUIZ_ITEM",
                )
            merged[ans.item_id] = ans.choice_id
        elif isinstance(question, UseInContextQuestion):
            if ans.text is None:
                raise ValidationAppError(
                    f"Question '{ans.item_id}' requires a text response.",
                    code="INVALID_QUIZ_ITEM",
                )
            merged[ans.item_id] = ans.text.strip()

    serialized: list[dict[str, str]] = []
    for q in questions:
        if q.item_id not in merged:
            continue
        val = merged[q.item_id]
        if isinstance(q, UseInContextQuestion):
            serialized.append({"item_id": q.item_id, "text": val})
        else:
            serialized.append({"item_id": q.item_id, "choice_id": val})
    return merged, serialized


def _build_session_response(
    submission: PracticeSubmission,
    questions: list[VocabQuizQuestion],
) -> VocabPracticeSessionResponse:
    objective_result: ObjectiveQuizResult | None = None
    context_result: list[ContextUsageFeedback] | None = None
    eval_status = None

    if submission.status == "ACCEPTED":
        eval_status = submission.evaluation_status
        feedback = submission.feedback if isinstance(submission.feedback, dict) else {}
        raw_obj = feedback.get("objective_result")
        if isinstance(raw_obj, dict):
            objective_result = ObjectiveQuizResult.model_validate(raw_obj)
        raw_ctx = feedback.get("context_result")
        if isinstance(raw_ctx, list):
            context_result = [
                ContextUsageFeedback.model_validate(item) for item in raw_ctx
            ]

    return VocabPracticeSessionResponse(
        id=submission.id,
        status=submission.status,
        mode="VOCAB_QUIZ",
        edit_version=submission.edit_version,
        questions=questions,
        saved_answers=extract_saved_answers(submission.input),
        evaluation_status=eval_status,
        objective_result=objective_result,
        context_result=context_result,
    )


class VocabPracticeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_session(
        self, user_id: UUID, session_id: UUID
    ) -> VocabPracticeSessionResponse:
        submission = await self.session.scalar(
            select(PracticeSubmission).where(
                PracticeSubmission.id == session_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "VOCAB_QUIZ",
            )
        )
        if submission is None:
            raise NotFoundError("Vocabulary practice session not found.")

        lesson_item = await self.session.scalar(
            select(ContentItem).where(
                ContentItem.id == submission.content_item_id,
                ContentItem.module == "VOCABULARY",
                ContentItem.kind == "VOCABULARY_LESSON",
                ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
            )
        )
        if lesson_item is None:
            raise ServiceUnavailableError(
                "The saved vocabulary quiz content is unavailable.",
                code="VOCABULARY_LESSON_UNAVAILABLE",
            )
        try:
            questions = project_public_questions(lesson_item)
            return _build_session_response(submission, questions)
        except (ValidationError, ValueError, TypeError):
            logger.error(
                "vocab_session_inconsistent user_id=%s session_id=%s",
                user_id,
                session_id,
            )
            raise ServiceUnavailableError(
                "The saved vocabulary quiz is incomplete. Please try again later.",
                code="VOCABULARY_LESSON_UNAVAILABLE",
            ) from None

    async def save_answers(
        self,
        user_id: UUID,
        session_id: UUID,
        payload: SaveVocabPracticeAnswersRequest,
    ) -> SaveVocabPracticeAnswersResponse:
        try:
            result = await self._save_answers(user_id, session_id, payload)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _save_answers(
        self,
        user_id: UUID,
        session_id: UUID,
        payload: SaveVocabPracticeAnswersRequest,
    ) -> SaveVocabPracticeAnswersResponse:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.id == session_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "VOCAB_QUIZ",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if draft is None:
            raise NotFoundError("Vocabulary practice session not found.")
        if draft.status != "DRAFT":
            raise ConflictError(
                "Submitted vocabulary practice sessions cannot be edited.",
                code="PRACTICE_NOT_EDITABLE",
            )

        lesson_item = await self.session.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == draft.content_item_id,
                ContentItem.module == "VOCABULARY",
                ContentItem.kind == "VOCABULARY_LESSON",
                ContentItem.status == "PUBLISHED",
            )
            .with_for_update(read=True)
        )
        if lesson_item is None:
            raise ServiceUnavailableError(
                "Assigned vocabulary lesson content is unavailable.",
                code="VOCABULARY_LESSON_UNAVAILABLE",
            )

        try:
            questions = project_public_questions(lesson_item)
        except (ValidationError, ValueError, TypeError):
            raise ServiceUnavailableError(
                "The saved vocabulary quiz is incomplete. Please try again later.",
                code="VOCABULARY_LESSON_UNAVAILABLE",
            ) from None

        existing_answers = extract_saved_answers(draft.input)
        merged, serialized = _validate_and_merge_answers(
            questions, existing_answers, payload
        )

        if payload.expected_edit_version != draft.edit_version:
            if (
                payload.expected_edit_version == draft.edit_version - 1
                and existing_answers == merged
            ):
                return SaveVocabPracticeAnswersResponse(
                    id=draft.id,
                    status="DRAFT",
                    edit_version=draft.edit_version,
                    saved_answer_count=len(existing_answers),
                )
            raise ConflictError(
                "The quiz draft has changed. Reload its current version.",
                code="STALE_EDIT_VERSION",
            )

        current_input = draft.input if isinstance(draft.input, dict) else {}
        draft.input = {
            **current_input,
            "answers": serialized,
        }
        draft.edit_version += 1
        return SaveVocabPracticeAnswersResponse(
            id=draft.id,
            status="DRAFT",
            edit_version=draft.edit_version,
            saved_answer_count=len(merged),
        )

    async def submit(
        self,
        user_id: UUID,
        session_id: UUID,
        idempotency_key: str,
        payload: SubmitVocabPracticeRequest | None = None,
    ) -> SubmitVocabPracticeResponse:
        try:
            result = await self._submit(user_id, session_id, idempotency_key, payload)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _submit(
        self,
        user_id: UUID,
        session_id: UUID,
        idempotency_key: str,
        payload: SubmitVocabPracticeRequest | None = None,
    ) -> SubmitVocabPracticeResponse:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Reject idempotency key reuse across different quiz sessions.
        other_feedbacks = await self.session.scalars(
            select(PracticeSubmission.feedback).where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "VOCAB_QUIZ",
                PracticeSubmission.id != session_id,
            )
        )
        for fb in other_feedbacks:
            if not isinstance(fb, dict):
                continue
            if key_hash in (fb.get("submit_key_hashes") or []):
                raise ConflictError(
                    "This key was used for a different vocabulary quiz submission.",
                    code="IDEMPOTENCY_KEY_REUSED",
                )

        # Standard lock order: user -> (plan, progress) -> content -> draft
        await self.session.execute(
            select(LearningPlan, ModuleProgress)
            .join(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "VOCABULARY",
            )
            .with_for_update(of=(LearningPlan, ModuleProgress))
            .execution_options(populate_existing=True)
        )

        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.id == session_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "VOCAB_QUIZ",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if draft is None:
            raise NotFoundError("Vocabulary practice session not found.")

        if draft.status == "ACCEPTED":
            fb = draft.feedback if isinstance(draft.feedback, dict) else {}
            receipt = fb.get("submit_response")
            if not isinstance(receipt, dict):
                raise ConflictError(
                    "The saved vocabulary submission receipt is missing.",
                    code="VOCABULARY_STATE_INCONSISTENT",
                )
            hashes = list(fb.get("submit_key_hashes") or [])
            if key_hash not in hashes:
                hashes.append(key_hash)
                draft.feedback = {**fb, "submit_key_hashes": hashes}
            return SubmitVocabPracticeResponse.model_validate(receipt)

        if draft.status != "DRAFT":
            raise ConflictError(
                "This practice session cannot be submitted in its current state.",
                code="PRACTICE_NOT_SUBMITTABLE",
            )

        progress = await self.session.get(ModuleProgress, draft.module_progress_id)
        if progress is None or progress.status != "ACTIVE":
            raise ConflictError(
                "Vocabulary enrollment is not active.",
                code="PRACTICE_NOT_SUBMITTABLE",
            )
        plan = await self.session.get(LearningPlan, progress.learning_plan_id)
        if plan is None or plan.status != "ACTIVE":
            raise ConflictError(
                "Active learning plan not found.",
                code="PRACTICE_NOT_SUBMITTABLE",
            )

        lesson_item = await self.session.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == draft.content_item_id,
                ContentItem.release_key == progress.content_release,
                ContentItem.module == "VOCABULARY",
                ContentItem.kind == "VOCABULARY_LESSON",
                ContentItem.slot == "CORE",
                ContentItem.cycle == plan.cycle,
                ContentItem.day == progress.current_day,
                ContentItem.cefr_level == progress.cefr_level,
                ContentItem.goal_variant == progress.goal_variant,
                ContentItem.status == "PUBLISHED",
            )
            .with_for_update(read=True)
        )
        if lesson_item is None:
            raise ConflictError(
                "This quiz does not match the currently assigned vocabulary lesson.",
                code="ACTIVITY_NOT_CURRENT",
            )

        try:
            questions = project_public_questions(lesson_item)
            word_ids = _parse_word_ids(lesson_item.body.get("word_content_ids"))
        except (ValidationError, ValueError, TypeError):
            raise ServiceUnavailableError(
                "The saved vocabulary quiz is incomplete. Please try again later.",
                code="VOCABULARY_LESSON_UNAVAILABLE",
            ) from None

        repo = VocabularyRepository(self.session)
        word_items = await repo.published_words(word_ids)
        if len(word_items) != TARGET_DAILY_WORD_COUNT:
            raise ConflictError(
                "The required vocabulary curriculum content is not available.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )

        credited_days = set(
            await self.session.scalars(
                select(ContentItem.day)
                .join(
                    ActivityCompletion,
                    ActivityCompletion.content_item_id == ContentItem.id,
                )
                .where(
                    ActivityCompletion.user_id == user_id,
                    ActivityCompletion.module_progress_id == progress.id,
                    ContentItem.release_key == progress.content_release,
                    ContentItem.module == "VOCABULARY",
                    ContentItem.kind == "VOCABULARY_LESSON",
                    ContentItem.slot == "CORE",
                    ContentItem.cycle == plan.cycle,
                    ContentItem.cefr_level == progress.cefr_level,
                    ContentItem.goal_variant == progress.goal_variant,
                    ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
                )
            )
        )
        day = progress.current_day
        if credited_days != set(range(1, day)):
            raise ConflictError(
                "Vocabulary progress and completion credits disagree.",
                code="VOCABULARY_STATE_INCONSISTENT",
            )

        saved_answers = extract_saved_answers(draft.input)
        if payload is not None and payload.answers:
            merged, serialized = _validate_and_merge_answers(
                questions,
                saved_answers,
                SaveVocabPracticeAnswersRequest(
                    expected_edit_version=draft.edit_version,
                    answers=payload.answers,
                ),
            )
            current_input = draft.input if isinstance(draft.input, dict) else {}
            draft.input = {**current_input, "answers": serialized}
            draft.edit_version += 1
            saved_answers = merged

        objective_result, graded_items, has_context = grade_objective_exercises(
            lesson_item, saved_answers
        )

        now = datetime.now(UTC)
        await self._upsert_lesson_words(user_id, word_items, now)

        draft.status = "ACCEPTED"
        draft.submitted_at = now
        draft.evaluation_status = "PENDING" if has_context else "NOT_REQUIRED"
        if objective_result.total > 0:
            draft.score = (
                Decimal(objective_result.correct)
                * Decimal(100)
                / Decimal(objective_result.total)
            ).quantize(Decimal("0.01"))

        self.session.add(
            ActivityCompletion(
                user_id=user_id,
                module_progress_id=progress.id,
                content_item_id=lesson_item.id,
                source_submission_id=draft.id,
                local_practice_date=now.astimezone(ZoneInfo(user.timezone)).date(),
                completed_at=now,
            )
        )

        next_day: int | None
        if day == 21:
            progress.status = "COMPLETED"
            progress.completed_at = now
            next_day = None
        else:
            progress.current_day = day + 1
            next_day = day + 1
        progress.updated_at = now

        job_id: UUID | None = None
        if has_context:
            job = AiJob(
                id=uuid4(),
                user_id=user_id,
                job_type="VOCAB_CONTEXT",
                practice_submission_id=draft.id,
                status="PENDING",
                idempotency_key=f"vocab:{draft.id}:context:v1",
            )
            self.session.add(job)
            await self.session.flush()
            job_id = job.id
            self.session.add(
                OutboxEvent(
                    ai_job_id=job.id,
                    event_type="VOCAB_CONTEXT_REQUESTED",
                    payload={
                        "job_id": str(job.id),
                        "practice_submission_id": str(draft.id),
                    },
                )
            )

        response = SubmitVocabPracticeResponse(
            id=draft.id,
            activity_status="COMPLETED",
            evaluation_status=draft.evaluation_status,
            objective_result=objective_result,
            context_result=None,
            job_id=job_id,
            next_module_day=next_day,
        )
        draft.feedback = {
            "objective_result": objective_result.model_dump(mode="json"),
            "graded_items": graded_items,
            "context_result": None,
            "submit_response": response.model_dump(mode="json"),
            "submit_key_hashes": [key_hash],
        }
        return response

    async def _upsert_lesson_words(
        self,
        user_id: UUID,
        word_items: list[ContentItem],
        now: datetime,
    ) -> None:
        word_ids = [item.id for item in word_items]
        word_keys = [
            str(item.body.get("word", "")).strip().lower()
            for item in word_items
            if isinstance(item.body, dict) and item.body.get("word")
        ]
        existing = await VocabularyRepository(self.session).user_vocab_for_words(
            user_id, word_ids, word_keys, for_update=True
        )
        by_key = {row.word_key.lower(): row for row in existing}
        by_id = {
            row.word_content_id: row
            for row in existing
            if row.word_content_id is not None
        }

        status, level, interval, next_review = initial_word_schedule(now)
        for item in word_items:
            raw_word = str(item.body.get("word", "")).strip()
            norm_key = raw_word.lower()
            row = by_id.get(item.id) or by_key.get(norm_key)
            if row is None:
                self.session.add(
                    UserVocabulary(
                        id=uuid4(),
                        user_id=user_id,
                        word_content_id=item.id,
                        word_key=norm_key,
                        status=status,
                        mastery_level=level,
                        review_interval_days=interval,
                        next_review_at=next_review,
                        times_practiced=1,
                        learned_at=now,
                        last_reviewed_at=now,
                    )
                )
            else:
                if row.word_content_id is None:
                    row.word_content_id = item.id
                if row.status in ("SUGGESTED", "DISMISSED"):
                    row.status = status
                    row.mastery_level = level
                    row.review_interval_days = interval
                    row.next_review_at = next_review
                    row.learned_at = row.learned_at or now
                elif row.next_review_at is None and row.status != "MASTERED":
                    row.review_interval_days = interval
                    row.next_review_at = next_review
                row.times_practiced = (row.times_practiced or 0) + 1
                row.last_reviewed_at = now

    async def create_or_resume(
        self, user_id: UUID, lesson_content_id: UUID, idempotency_key: str
    ) -> tuple[VocabPracticeSessionResponse, bool]:
        try:
            result = await self._create_or_resume(
                user_id, lesson_content_id, idempotency_key
            )
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _create_or_resume(
        self, user_id: UUID, lesson_content_id: UUID, idempotency_key: str
    ) -> tuple[VocabPracticeSessionResponse, bool]:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Lock plan and VOCABULARY module progress in the standard lock order.
        await self.session.execute(
            select(LearningPlan, ModuleProgress)
            .join(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "VOCABULARY",
            )
            .with_for_update(of=(LearningPlan, ModuleProgress))
            .execution_options(populate_existing=True)
        )

        # Reject idempotency key reuse across different lesson IDs.
        other_inputs = await self.session.scalars(
            select(PracticeSubmission.input).where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "VOCAB_QUIZ",
                PracticeSubmission.content_item_id != lesson_content_id,
            )
        )
        for inp in other_inputs:
            if not isinstance(inp, dict):
                continue
            saved_hashes = inp.get("create_key_hashes") or []
            if inp.get("create_key_hash") == key_hash or key_hash in saved_hashes:
                raise ConflictError(
                    "This key was used with a different request.",
                    code="IDEMPOTENCY_KEY_REUSED",
                )

        today = await VocabularyQueryService(self.session).get_today(user_id)
        if today.lesson is None or today.module_status == "COMPLETED":
            raise ConflictError(
                "Vocabulary is already completed.",
                code="ACTIVITY_ALREADY_COMPLETED",
            )

        credited = await self.session.scalar(
            select(ActivityCompletion.id).where(
                ActivityCompletion.user_id == user_id,
                ActivityCompletion.module_progress_id == today.module_progress_id,
                ActivityCompletion.content_item_id == lesson_content_id,
            )
        )
        if credited is not None:
            raise ConflictError(
                "This vocabulary lesson has already been completed.",
                code="ACTIVITY_ALREADY_COMPLETED",
            )

        if lesson_content_id != today.lesson.id:
            raise ConflictError(
                "Choose the currently assigned vocabulary lesson.",
                code="ACTIVITY_NOT_CURRENT",
            )

        lesson_item = await self.session.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == lesson_content_id,
                ContentItem.module == "VOCABULARY",
                ContentItem.kind == "VOCABULARY_LESSON",
                ContentItem.status == "PUBLISHED",
            )
            .with_for_update(read=True)
        )
        if lesson_item is None:
            raise ConflictError(
                "The required vocabulary curriculum content is not available.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )

        try:
            questions = project_public_questions(lesson_item)
        except (ValidationError, ValueError, TypeError):
            logger.error(
                "vocabulary_quiz_inconsistent user_id=%s lesson_id=%s",
                user_id,
                lesson_content_id,
            )
            raise ServiceUnavailableError(
                "The saved vocabulary quiz is incomplete. Please try again later.",
                code="VOCABULARY_LESSON_UNAVAILABLE",
            ) from None

        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.module_progress_id == today.module_progress_id,
                PracticeSubmission.content_item_id == lesson_content_id,
                PracticeSubmission.mode == "VOCAB_QUIZ",
                PracticeSubmission.status == "DRAFT",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        created = draft is None
        if draft is None:
            draft = PracticeSubmission(
                id=uuid4(),
                user_id=user_id,
                module_progress_id=today.module_progress_id,
                content_item_id=lesson_content_id,
                mode="VOCAB_QUIZ",
                status="DRAFT",
                evaluation_status="NOT_REQUIRED",
                edit_version=0,
                revision_number=1,
                input={
                    "answers": [],
                    "create_key_hash": key_hash,
                    "create_key_hashes": [key_hash],
                },
            )
            self.session.add(draft)
            await self.session.flush()
        else:
            current_input = draft.input if isinstance(draft.input, dict) else {}
            hashes = list(current_input.get("create_key_hashes") or [])
            if key_hash not in hashes:
                hashes.append(key_hash)
                draft.input = {**current_input, "create_key_hashes": hashes}

        return _build_session_response(draft, questions), created

    async def submit_review(
        self,
        user_id: UUID,
        payload: SubmitVocabReviewRequest,
        idempotency_key: str,
    ) -> SubmitVocabReviewResponse:
        try:
            result = await self._submit_review(user_id, payload, idempotency_key)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _submit_review(
        self,
        user_id: UUID,
        payload: SubmitVocabReviewRequest,
        idempotency_key: str,
    ) -> SubmitVocabReviewResponse:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
        normalized_answer = payload.answer.model_dump(exclude_none=True)

        existing_reviews = list(
            await self.session.scalars(
                select(PracticeSubmission).where(
                    PracticeSubmission.user_id == user_id,
                    PracticeSubmission.mode == "VOCAB_REVIEW",
                )
            )
        )
        for rev in existing_reviews:
            inp = rev.input if isinstance(rev.input, dict) else {}
            if inp.get("idempotency_key_hash") != key_hash:
                continue
            if (
                inp.get("user_vocabulary_id") != str(payload.user_vocabulary_id)
                or inp.get("answer") != normalized_answer
            ):
                raise ConflictError(
                    "This key was used with a different vocabulary review request.",
                    code="IDEMPOTENCY_KEY_REUSED",
                )
            fb = rev.feedback if isinstance(rev.feedback, dict) else {}
            receipt = fb.get("review_response")
            if isinstance(receipt, dict):
                return SubmitVocabReviewResponse.model_validate(receipt)
            raise ConflictError(
                "The saved vocabulary review receipt is missing.",
                code="VOCABULARY_STATE_INCONSISTENT",
            )

        user_vocab = await self.session.scalar(
            select(UserVocabulary)
            .where(
                UserVocabulary.id == payload.user_vocabulary_id,
                UserVocabulary.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user_vocab is None:
            raise NotFoundError("Vocabulary review item not found.")

        now = datetime.now(UTC)
        next_rev = user_vocab.next_review_at
        if next_rev is not None and next_rev.tzinfo is None:
            next_rev = next_rev.replace(tzinfo=UTC)

        if (
            user_vocab.status not in ("LEARNING", "REVIEWING")
            or next_rev is None
            or next_rev > now
        ):
            raise ConflictError(
                "This vocabulary word is not currently due for review.",
                code="REVIEW_NOT_DUE",
            )

        if user_vocab.word_content_id is None:
            raise ConflictError(
                "The vocabulary word content for this review is unavailable.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )

        word_item = await self.session.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == user_vocab.word_content_id,
                ContentItem.module == "VOCABULARY",
                ContentItem.kind == "VOCAB_WORD",
                ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
            )
            .with_for_update(read=True)
        )
        if word_item is None:
            raise ConflictError(
                "The vocabulary word content for this review is unavailable.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )

        correct = grade_recall_review(word_item, payload.answer)
        srs_update = apply_review_outcome(
            current_mastery_level=user_vocab.mastery_level,
            times_practiced=user_vocab.times_practiced,
            correct=correct,
            now=now,
            existing_mastered_at=user_vocab.mastered_at,
        )

        user_vocab.status = srs_update.status
        user_vocab.mastery_level = srs_update.mastery_level
        user_vocab.review_interval_days = srs_update.review_interval_days
        user_vocab.next_review_at = srs_update.next_review_at
        user_vocab.last_reviewed_at = srs_update.last_reviewed_at
        user_vocab.mastered_at = srs_update.mastered_at
        user_vocab.times_practiced = srs_update.times_practiced

        active_progress_id = await self.session.scalar(
            select(ModuleProgress.id)
            .join(LearningPlan, LearningPlan.id == ModuleProgress.learning_plan_id)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "VOCABULARY",
            )
        )

        prior_review_count = int(
            await self.session.scalar(
                select(func.count(PracticeSubmission.id)).where(
                    PracticeSubmission.user_id == user_id,
                    PracticeSubmission.mode == "VOCAB_REVIEW",
                    PracticeSubmission.content_item_id == word_item.id,
                )
            )
            or 0
        )
        times_reviewed = max(prior_review_count + 1, srs_update.times_practiced - 1)

        response = SubmitVocabReviewResponse(
            user_vocabulary_id=user_vocab.id,
            correct=correct,
            previous_mastery_level=srs_update.previous_mastery_level,
            mastery_level=srs_update.mastery_level,
            status=srs_update.status,
            next_review_at=srs_update.next_review_at,
            times_reviewed=times_reviewed,
        )

        submission = PracticeSubmission(
            id=uuid4(),
            user_id=user_id,
            module_progress_id=active_progress_id,
            content_item_id=word_item.id,
            mode="VOCAB_REVIEW",
            status="ACCEPTED",
            evaluation_status="NOT_REQUIRED",
            edit_version=0,
            revision_number=1,
            score=Decimal("100.00") if correct else Decimal("0.00"),
            submitted_at=now,
            input={
                "user_vocabulary_id": str(user_vocab.id),
                "answer": normalized_answer,
                "idempotency_key_hash": key_hash,
            },
            feedback={
                "correct": correct,
                "previous_mastery_level": srs_update.previous_mastery_level,
                "mastery_level": srs_update.mastery_level,
                "review_response": response.model_dump(mode="json"),
            },
        )
        self.session.add(submission)
        await self.session.flush()
        return response


def grade_recall_review(
    word_item: ContentItem,
    answer: SubmitVocabReviewAnswer,
) -> bool:
    """Grade a RECALL review submission against server-held word content."""
    body = word_item.body if isinstance(word_item.body, dict) else {}
    raw_ex = body.get("review_exercise")
    answer_key = body.get("answer_key") if isinstance(body.get("answer_key"), dict) else {}

    if isinstance(raw_ex, dict):
        raw_choices = raw_ex.get("choices")
        valid_ids: set[str] | None = None
        if isinstance(raw_choices, list) and raw_choices:
            valid_ids = {
                str(opt["id"])
                for opt in raw_choices
                if isinstance(opt, dict) and isinstance(opt.get("id"), str)
            }
        correct_id = (
            raw_ex.get("correct_choice_id")
            or answer_key.get("review_choice_id")
            or answer_key.get("correct_choice_id")
        )
        if not isinstance(correct_id, str) or not correct_id.strip():
            raise ServiceUnavailableError(
                "The saved vocabulary review exercise is incomplete.",
                code="VOCABULARY_REVIEW_UNAVAILABLE",
            )
        if answer.selected_choice_id is None:
            raise ValidationAppError(
                "A choice selection is required for this review exercise.",
                code="INVALID_REVIEW_ANSWER",
            )
        if valid_ids is not None and answer.selected_choice_id not in valid_ids:
            raise ValidationAppError(
                "The selected choice is not valid for this review exercise.",
                code="INVALID_REVIEW_ANSWER",
            )
        return answer.selected_choice_id == correct_id.strip()

    explicit_correct = (
        answer_key.get("correct_choice_id")
        or answer_key.get("review_choice_id")
        or body.get("correct_choice_id")
    )
    if isinstance(explicit_correct, str) and explicit_correct.strip():
        if answer.selected_choice_id is None:
            raise ValidationAppError(
                "A choice selection is required for this review exercise.",
                code="INVALID_REVIEW_ANSWER",
            )
        return answer.selected_choice_id == explicit_correct.strip()

    # Fallback when VOCAB_WORD contains standard card metadata without an explicit choices block.
    definition = str(body.get("definition", "")).strip()
    word_text = str(body.get("word", "")).strip()
    if answer.selected_choice_id is not None:
        candidate = answer.selected_choice_id.strip()
        return candidate == "correct_choice" or (
            bool(definition) and candidate.lower() == definition.lower()
        )
    if answer.text is not None:
        candidate_text = answer.text.strip().lower()
        return bool(
            (definition and candidate_text == definition.lower())
            or (word_text and candidate_text == word_text.lower())
        )
    return False

