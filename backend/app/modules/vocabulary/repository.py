"""Read-only queries for daily vocabulary lessons, word cards, and due counts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.content.models import ContentItem
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.learning.repository import today_plan_statement
from app.modules.practice.models import PracticeSubmission
from app.modules.vocabulary.models import UserVocabulary


def vocabulary_today_statement(user_id: UUID):
    draft_id = (
        select(PracticeSubmission.id)
        .where(
            PracticeSubmission.user_id == user_id,
            PracticeSubmission.module_progress_id == ModuleProgress.id,
            PracticeSubmission.content_item_id == ContentItem.id,
            PracticeSubmission.mode == "VOCAB_QUIZ",
            PracticeSubmission.status == "DRAFT",
        )
        .order_by(PracticeSubmission.created_at.desc(), PracticeSubmission.id.desc())
        .limit(1)
        .correlate(ModuleProgress, ContentItem)
        .scalar_subquery()
    )
    due_reviews = (
        select(func.count(UserVocabulary.id))
        .where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.status.in_(("LEARNING", "REVIEWING")),
            UserVocabulary.next_review_at.is_not(None),
            UserVocabulary.next_review_at <= func.now(),
        )
        .scalar_subquery()
    )
    return today_plan_statement(user_id).add_columns(
        ContentItem.body["word_content_ids"].label("word_content_ids"),
        draft_id.label("existing_practice_session_id"),
        due_reviews.label("due_review_count"),
    )


class VocabularyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def today(self, user_id: UUID):
        return (await self.session.execute(vocabulary_today_statement(user_id))).all()

    async def published_words(self, word_ids: list[UUID]) -> list[ContentItem]:
        if not word_ids:
            return []
        stmt = select(ContentItem).where(
            ContentItem.id.in_(word_ids),
            ContentItem.module == "VOCABULARY",
            ContentItem.kind == "VOCAB_WORD",
            ContentItem.status == "PUBLISHED",
        )
        return list(await self.session.scalars(stmt))

    async def user_vocab_for_words(
        self,
        user_id: UUID,
        word_ids: list[UUID],
        word_keys: list[str],
        *,
        for_update: bool = False,
    ) -> list[UserVocabulary]:
        conditions = []
        if word_ids:
            conditions.append(UserVocabulary.word_content_id.in_(word_ids))
        if word_keys:
            conditions.append(
                func.lower(UserVocabulary.word_key).in_(
                    [k.lower() for k in word_keys]
                )
            )
        if not conditions:
            return []
        stmt = (
            select(UserVocabulary)
            .where(
                UserVocabulary.user_id == user_id,
                or_(*conditions),
            )
            .order_by(UserVocabulary.id.asc())
        )
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return list(await self.session.scalars(stmt))

    async def published_word(self, word_id: UUID) -> ContentItem | None:
        return await self.session.scalar(
            select(ContentItem).where(
                ContentItem.id == word_id,
                ContentItem.module == "VOCABULARY",
                ContentItem.kind == "VOCAB_WORD",
                ContentItem.status == "PUBLISHED",
            )
        )

    async def assigned_lesson_word_ids(self, user_id: UUID) -> set[UUID]:
        """Return word IDs from published lessons up to the learner's current day."""
        stmt = (
            select(ContentItem.body["word_content_ids"])
            .select_from(LearningPlan)
            .join(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
            .join(
                ContentItem,
                (ContentItem.release_key == ModuleProgress.content_release)
                & (ContentItem.module == "VOCABULARY")
                & (ContentItem.kind == "VOCABULARY_LESSON")
                & (ContentItem.cycle == LearningPlan.cycle)
                & (ContentItem.cefr_level == ModuleProgress.cefr_level)
                & (ContentItem.goal_variant == ModuleProgress.goal_variant)
                & (ContentItem.slot == "CORE")
                & (ContentItem.status.in_(("PUBLISHED", "ARCHIVED")))
                & (ContentItem.day <= ModuleProgress.current_day),
            )
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "VOCABULARY",
            )
        )
        result: set[UUID] = set()
        for raw_list in await self.session.scalars(stmt):
            if isinstance(raw_list, list):
                for raw in raw_list:
                    try:
                        result.add(raw if isinstance(raw, UUID) else UUID(str(raw)))
                    except (ValueError, TypeError):
                        continue
        return result

    async def due_reviews(
        self,
        user_id: UUID,
        *,
        now: datetime,
        limit: int,
        cursor_point: tuple[datetime, UUID] | None = None,
    ) -> list[tuple[UserVocabulary, ContentItem | None]]:
        """Fetch due and overdue user_vocabulary rows ordered by (next_review_at, id)."""
        stmt = (
            select(UserVocabulary, ContentItem)
            .outerjoin(
                ContentItem,
                and_(
                    ContentItem.id == UserVocabulary.word_content_id,
                    ContentItem.module == "VOCABULARY",
                    ContentItem.kind == "VOCAB_WORD",
                    ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
                ),
            )
            .where(
                UserVocabulary.user_id == user_id,
                UserVocabulary.status.in_(("LEARNING", "REVIEWING")),
                UserVocabulary.next_review_at.is_not(None),
                UserVocabulary.next_review_at <= now,
            )
        )
        if cursor_point is not None:
            cursor_dt, cursor_id = cursor_point
            stmt = stmt.where(
                or_(
                    UserVocabulary.next_review_at > cursor_dt,
                    and_(
                        UserVocabulary.next_review_at == cursor_dt,
                        UserVocabulary.id > cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            UserVocabulary.next_review_at.asc(),
            UserVocabulary.id.asc(),
        ).limit(limit + 1)
        rows = (await self.session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def bank_words(
        self,
        user_id: UUID,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int = 20,
        cursor_point: tuple[str, UUID] | None = None,
    ) -> list[UserVocabulary]:
        """Fetch cursor-paginated personal vocabulary bank rows ordered by (word_key, id)."""
        stmt = select(UserVocabulary).where(UserVocabulary.user_id == user_id)
        if status is not None:
            stmt = stmt.where(UserVocabulary.status == status)
        else:
            stmt = stmt.where(
                UserVocabulary.status.in_(("LEARNING", "REVIEWING", "MASTERED"))
            )
        if search:
            stmt = stmt.where(
                func.lower(UserVocabulary.word_key).contains(
                    search.strip().lower(), autoescape=True
                )
            )
        if cursor_point is not None:
            cursor_word, cursor_id = cursor_point
            stmt = stmt.where(
                or_(
                    UserVocabulary.word_key > cursor_word,
                    and_(
                        UserVocabulary.word_key == cursor_word,
                        UserVocabulary.id > cursor_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            UserVocabulary.word_key.asc(),
            UserVocabulary.id.asc(),
        ).limit(limit + 1)
        return list(await self.session.scalars(stmt))

    async def progress_stats(
        self,
        user_id: UUID,
        *,
        module_progress_id: UUID,
        now: datetime,
        start_of_local_day_utc: datetime,
    ) -> dict[str, int]:
        """Aggregate vocabulary retention, review queue, and curriculum completion stats."""
        active_review = and_(
            UserVocabulary.status.in_(("LEARNING", "REVIEWING")),
            UserVocabulary.next_review_at.is_not(None),
        )
        vocab_stmt = select(
            func.coalesce(
                func.sum(case((UserVocabulary.status == "MASTERED", 1), else_=0)), 0
            ).label("mastered"),
            func.coalesce(
                func.sum(case((UserVocabulary.status == "LEARNING", 1), else_=0)), 0
            ).label("learning"),
            func.coalesce(
                func.sum(case((UserVocabulary.status == "REVIEWING", 1), else_=0)), 0
            ).label("reviewing"),
            func.coalesce(
                func.sum(
                    case(
                        (and_(active_review, UserVocabulary.next_review_at <= now), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("due_reviews"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                active_review,
                                UserVocabulary.next_review_at < start_of_local_day_utc,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("overdue_reviews"),
        ).where(UserVocabulary.user_id == user_id)

        vocab_row = (await self.session.execute(vocab_stmt)).one()

        completed_days = int(
            await self.session.scalar(
                select(func.count(ActivityCompletion.id)).where(
                    ActivityCompletion.user_id == user_id,
                    ActivityCompletion.module_progress_id == module_progress_id,
                )
            )
            or 0
        )
        mastered = int(vocab_row.mastered or 0)
        learning = int(vocab_row.learning or 0)
        reviewing = int(vocab_row.reviewing or 0)
        return {
            "learned_distinct": mastered + learning + reviewing,
            "mastered": mastered,
            "learning": learning,
            "reviewing": reviewing,
            "due_reviews": int(vocab_row.due_reviews or 0),
            "overdue_reviews": int(vocab_row.overdue_reviews or 0),
            "completed_curriculum_days": min(21, completed_days),
        }


