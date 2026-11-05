"""Read-only daily vocabulary assignment, 10-word lesson projection, and word detail."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationAppError,
)
from app.modules.content.models import ContentItem
from app.modules.learning.service import LearningPlanQueryService
from app.modules.vocabulary.models import UserVocabulary
from app.modules.vocabulary.repository import VocabularyRepository
from app.modules.vocabulary.schemas import (
    DueReviewExercise,
    DueReviewItem,
    DueReviewsResponse,
    MatchChoiceOption,
    VocabularyBankItem,
    VocabularyBankResponse,
    VocabularyBankStatus,
    VocabularyLesson,
    VocabularyProgressResponse,
    VocabularyTodayResponse,
    VocabularyWordCard,
    VocabularyWordDetailResponse,
)

logger = logging.getLogger(__name__)
TARGET_DAILY_WORD_COUNT = 10


def _parse_word_ids(raw_ids: object) -> list[UUID]:
    if not isinstance(raw_ids, list) or len(raw_ids) != TARGET_DAILY_WORD_COUNT:
        raise ValueError("A vocabulary lesson must reference exactly 10 word IDs.")
    parsed: list[UUID] = []
    for raw in raw_ids:
        parsed.append(raw if isinstance(raw, UUID) else UUID(str(raw)))
    if len(set(parsed)) != TARGET_DAILY_WORD_COUNT:
        raise ValueError("A vocabulary lesson must reference 10 distinct word IDs.")
    return parsed


def _project_word_card(
    item: ContentItem, user_vocab: UserVocabulary | None
) -> VocabularyWordCard:
    body = item.body if isinstance(item.body, dict) else {}
    return VocabularyWordCard(
        id=item.id,
        word=body.get("word"),
        part_of_speech=body.get("part_of_speech"),
        definition=body.get("definition"),
        ipa=body.get("ipa"),
        examples=body.get("examples"),
        synonyms=body.get("synonyms") or [],
        antonyms=body.get("antonyms") or [],
        pronunciation_audio_url=body.get("pronunciation_audio_url"),
        mastery_status=user_vocab.status if user_vocab is not None else "NEW",
    )


def _encode_due_cursor(next_review_at: datetime, row_id: UUID) -> str:
    payload = json.dumps(
        {"t": next_review_at.astimezone(UTC).isoformat(), "id": str(row_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_due_cursor(cursor: str) -> tuple[datetime, UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if not isinstance(raw, dict):
            raise TypeError("Cursor payload must be an object.")
        dt = datetime.fromisoformat(str(raw["t"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        row_id = UUID(str(raw["id"]))
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise ValidationAppError(
            "Invalid pagination cursor.",
            code="INVALID_CURSOR",
        ) from None
    return dt, row_id


def _encode_bank_cursor(word_key: str, row_id: UUID) -> str:
    payload = json.dumps(
        {"w": word_key, "id": str(row_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_bank_cursor(cursor: str) -> tuple[str, UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if not isinstance(raw, dict):
            raise TypeError("Cursor payload must be an object.")
        word_key = str(raw["w"])
        if not word_key or len(word_key) > 120:
            raise ValueError("Invalid word_key in cursor.")
        row_id = UUID(str(raw["id"]))
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise ValidationAppError(
            "Invalid pagination cursor.",
            code="INVALID_CURSOR",
        ) from None
    return word_key, row_id


def _project_due_review_exercise(
    word: str, content_item: ContentItem | None
) -> DueReviewExercise:
    prompt = f"What does '{word}' mean?"
    choices: list[MatchChoiceOption] | None = None
    if content_item is not None and isinstance(content_item.body, dict):
        raw_ex = content_item.body.get("review_exercise")
        if isinstance(raw_ex, dict):
            raw_prompt = raw_ex.get("prompt")
            if isinstance(raw_prompt, str) and raw_prompt.strip():
                prompt = raw_prompt.strip()
            raw_choices = raw_ex.get("choices")
            if isinstance(raw_choices, list) and 2 <= len(raw_choices) <= 6:
                parsed_choices: list[MatchChoiceOption] = []
                for opt in raw_choices:
                    if (
                        isinstance(opt, dict)
                        and isinstance(opt.get("id"), str)
                        and isinstance(opt.get("text"), str)
                    ):
                        parsed_choices.append(
                            MatchChoiceOption(id=opt["id"], text=opt["text"])
                        )
                if len(parsed_choices) == len(raw_choices):
                    choices = parsed_choices
    return DueReviewExercise(type="RECALL", prompt=prompt, choices=choices)


class VocabularyQueryService:
    def __init__(self, session: AsyncSession):
        self.repository = VocabularyRepository(session)
        self.learning = LearningPlanQueryService(session)

    async def get_today(self, user_id: UUID) -> VocabularyTodayResponse:
        rows = await self.repository.today(user_id)
        current = self.learning.current_response(user_id, rows)
        progress = next(
            (item for item in current.modules if item.module == "VOCABULARY"), None
        )
        if progress is None:
            raise NotFoundError(
                "Vocabulary is not enrolled in the active plan.",
                code="MODULE_NOT_ENROLLED",
            )
        row = next(r for r in rows if r.ModuleProgress.id == progress.progress_id)
        due_count = int(row.due_review_count or 0)

        if progress.status == "COMPLETED":
            return VocabularyTodayResponse(
                plan_id=current.plan.id,
                module_progress_id=progress.progress_id,
                cycle=current.plan.cycle,
                day=21,
                module_status="COMPLETED",
                lesson=None,
                existing_practice_session_id=None,
                due_review_count=due_count,
            )

        if progress.status != "ACTIVE" or row.content_item_id is None:
            raise ConflictError(
                "The required vocabulary curriculum content is not available.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )

        try:
            word_ids = _parse_word_ids(row.word_content_ids)
            items = await self.repository.published_words(word_ids)
            by_id = {item.id: item for item in items}

            if len(by_id) != TARGET_DAILY_WORD_COUNT:
                raise ConflictError(
                    "The required vocabulary curriculum content is not available.",
                    code="CURRICULUM_CONTENT_UNAVAILABLE",
                )

            word_keys = [
                str(item.body.get("word", "")).strip().lower()
                for item in items
                if isinstance(item.body, dict) and item.body.get("word")
            ]
            vocab_rows = await self.repository.user_vocab_for_words(
                user_id, word_ids, word_keys
            )
            by_content_id = {
                v.word_content_id: v for v in vocab_rows if v.word_content_id
            }
            by_word_key = {v.word_key.lower(): v for v in vocab_rows}

            words: list[VocabularyWordCard] = []
            for word_id in word_ids:
                item = by_id[word_id]
                raw_word = (
                    str(item.body.get("word", "")).strip().lower()
                    if isinstance(item.body, dict)
                    else ""
                )
                user_vocab = by_content_id.get(item.id) or by_word_key.get(raw_word)
                words.append(_project_word_card(item, user_vocab))

            lesson = VocabularyLesson(
                id=row.content_item_id,
                title=row.title,
                target_cefr=progress.target_cefr,
                target_word_count=10,
                words=words,
            )
            return VocabularyTodayResponse(
                plan_id=current.plan.id,
                module_progress_id=progress.progress_id,
                cycle=current.plan.cycle,
                day=progress.current_day,
                module_status="ACTIVE",
                lesson=lesson,
                existing_practice_session_id=row.existing_practice_session_id,
                due_review_count=due_count,
            )
        except ConflictError:
            raise
        except (ValidationError, ValueError, TypeError):
            logger.error(
                "vocabulary_lesson_inconsistent user_id=%s content_item_id=%s",
                user_id,
                row.content_item_id,
            )
            raise ServiceUnavailableError(
                "The saved vocabulary lesson is incomplete. Please try again later.",
                code="VOCABULARY_LESSON_UNAVAILABLE",
            ) from None

    async def get_word(
        self, user_id: UUID, word_id: UUID
    ) -> VocabularyWordDetailResponse:
        item = await self.repository.published_word(word_id)
        if item is None or not isinstance(item.body, dict):
            raise NotFoundError("Vocabulary word not found.")

        raw_word = str(item.body.get("word", "")).strip()
        vocab_rows = await self.repository.user_vocab_for_words(
            user_id, [word_id], [raw_word] if raw_word else []
        )
        user_vocab = next(
            (v for v in vocab_rows if v.word_content_id == word_id),
            vocab_rows[0] if vocab_rows else None,
        )

        if user_vocab is None:
            assigned_ids = await self.repository.assigned_lesson_word_ids(user_id)
            if word_id not in assigned_ids:
                raise NotFoundError("Vocabulary word not found.")

        try:
            card = _project_word_card(item, user_vocab)
            return VocabularyWordDetailResponse(
                **card.model_dump(),
                cefr_level=item.cefr_level,
                mastery_level=user_vocab.mastery_level if user_vocab else None,
                times_practiced=user_vocab.times_practiced if user_vocab else 0,
                next_review_at=user_vocab.next_review_at if user_vocab else None,
                last_reviewed_at=user_vocab.last_reviewed_at if user_vocab else None,
            )
        except ValidationError:
            logger.error(
                "vocabulary_word_inconsistent user_id=%s word_id=%s",
                user_id,
                word_id,
            )
            raise ServiceUnavailableError(
                "The saved vocabulary word is incomplete. Please try again later.",
                code="VOCABULARY_WORD_UNAVAILABLE",
            ) from None

    async def get_due_reviews(
        self,
        user_id: UUID,
        timezone_name: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> DueReviewsResponse:
        cursor_point = _decode_due_cursor(cursor) if cursor else None
        now_utc = datetime.now(UTC)
        user_tz = ZoneInfo(timezone_name)
        as_of = now_utc.astimezone(user_tz)

        rows = await self.repository.due_reviews(
            user_id,
            now=now_utc,
            limit=limit,
            cursor_point=cursor_point,
        )
        has_next = len(rows) > limit
        page_rows = rows[:limit]

        items: list[DueReviewItem] = []
        for user_vocab, content_item in page_rows:
            word_display = user_vocab.word_key
            if content_item is not None and isinstance(content_item.body, dict):
                raw_w = content_item.body.get("word")
                if isinstance(raw_w, str) and raw_w.strip():
                    word_display = raw_w.strip()

            next_rev = user_vocab.next_review_at
            if next_rev is None:
                continue
            if next_rev.tzinfo is None:
                next_rev = next_rev.replace(tzinfo=UTC)

            is_overdue = next_rev.astimezone(user_tz).date() < as_of.date()
            exercise = _project_due_review_exercise(word_display, content_item)
            items.append(
                DueReviewItem(
                    user_vocabulary_id=user_vocab.id,
                    word=word_display,
                    mastery_level=user_vocab.mastery_level,
                    status=user_vocab.status,
                    next_review_at=next_rev,
                    is_overdue=is_overdue,
                    exercise=exercise,
                )
            )

        next_cursor: str | None = None
        if has_next and page_rows:
            last_vocab = page_rows[-1][0]
            if last_vocab.next_review_at is not None:
                last_dt = (
                    last_vocab.next_review_at
                    if last_vocab.next_review_at.tzinfo is not None
                    else last_vocab.next_review_at.replace(tzinfo=UTC)
                )
                next_cursor = _encode_due_cursor(last_dt, last_vocab.id)

        return DueReviewsResponse(
            as_of=as_of,
            items=items,
            next_cursor=next_cursor,
        )

    async def get_bank(
        self,
        user_id: UUID,
        *,
        status: VocabularyBankStatus | None = None,
        search: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> VocabularyBankResponse:
        cursor_point = _decode_bank_cursor(cursor) if cursor else None
        rows = await self.repository.bank_words(
            user_id,
            status=status,
            search=search,
            limit=limit,
            cursor_point=cursor_point,
        )
        has_next = len(rows) > limit
        page_rows = rows[:limit]

        items = [
            VocabularyBankItem(
                word_key=row.word_key,
                word_content_id=row.word_content_id,
                status=row.status,
                mastery_level=row.mastery_level,
                times_practiced=row.times_practiced,
                next_review_at=row.next_review_at,
            )
            for row in page_rows
        ]
        next_cursor: str | None = None
        if has_next and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_bank_cursor(last.word_key, last.id)

        return VocabularyBankResponse(items=items, next_cursor=next_cursor)

    async def get_progress(
        self, user_id: UUID, timezone_name: str
    ) -> VocabularyProgressResponse:
        rows = await self.repository.today(user_id)
        current = self.learning.current_response(user_id, rows)
        progress = next(
            (item for item in current.modules if item.module == "VOCABULARY"), None
        )
        if progress is None:
            raise NotFoundError(
                "Vocabulary is not enrolled in the active plan.",
                code="MODULE_NOT_ENROLLED",
            )

        now_utc = datetime.now(UTC)
        user_tz = ZoneInfo(timezone_name)
        local_now = now_utc.astimezone(user_tz)
        start_of_local_day_utc = local_now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(UTC)

        stats = await self.repository.progress_stats(
            user_id,
            module_progress_id=progress.progress_id,
            now=now_utc,
            start_of_local_day_utc=start_of_local_day_utc,
        )
        return VocabularyProgressResponse(
            learned_distinct=stats["learned_distinct"],
            mastered=stats["mastered"],
            learning=stats["learning"],
            reviewing=stats["reviewing"],
            due_reviews=stats["due_reviews"],
            overdue_reviews=stats["overdue_reviews"],
            current_module_day=progress.current_day,
            completed_curriculum_days=stats["completed_curriculum_days"],
        )


