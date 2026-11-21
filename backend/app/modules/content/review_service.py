"""Admin editorial review service for listing, inspecting, and deciding on ContentItems."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.content.models import ContentItem
from app.modules.content.review_schemas import (
    AiReviewSummary,
    ContentItemDetail,
    ContentItemListResponse,
    ContentItemSummary,
    LinkedWordItem,
    ReviewDecisionRequest,
)
from app.modules.jobs.models import AiJob

LESSON_KINDS = ("VOCABULARY_LESSON", "SPEAKING_LESSON", "WRITING_LESSON")


def _to_summary(item: ContentItem) -> ContentItemSummary:
    return ContentItemSummary(
        id=item.id,
        kind=item.kind,
        module=item.module,
        release_key=item.release_key,
        cycle=item.cycle,
        day=item.day,
        cefr_level=item.cefr_level,
        goal_variant=item.goal_variant,
        title=item.title,
        status=item.status,
        origin=item.origin,
        generation_batch_key=item.generation_batch_key,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        review_notes=item.review_notes,
        created_at=item.created_at,
        published_at=item.published_at,
    )


class ContentReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_items(
        self,
        *,
        status: str | None = None,
        release_key: str | None = None,
        generation_batch_key: str | None = None,
        kind: str | None = None,
        origin: str | None = None,
        limit: int = 50,
    ) -> ContentItemListResponse:
        stmt = select(ContentItem)
        if kind:
            stmt = stmt.where(ContentItem.kind == kind)
        else:
            stmt = stmt.where(ContentItem.kind.in_(LESSON_KINDS))
        if status:
            stmt = stmt.where(ContentItem.status == status)
        if release_key:
            stmt = stmt.where(ContentItem.release_key == release_key)
        if generation_batch_key:
            stmt = stmt.where(ContentItem.generation_batch_key == generation_batch_key)
        if origin:
            stmt = stmt.where(ContentItem.origin == origin)

        rows = list(
            await self.db.scalars(
                stmt.order_by(
                    ContentItem.created_at.desc(),
                    ContentItem.day.asc().nullslast(),
                ).limit(limit)
            )
        )
        return ContentItemListResponse(
            items=[_to_summary(row) for row in rows],
            total=len(rows),
        )

    async def get_detail(self, item_id: UUID) -> ContentItemDetail:
        item = await self.db.get(ContentItem, item_id)
        if item is None:
            raise NotFoundError("Content item not found.")

        words: list[LinkedWordItem] = []
        raw_word_ids = (item.body or {}).get("word_content_ids")
        if item.kind == "VOCABULARY_LESSON" and isinstance(raw_word_ids, list):
            parsed_ids: list[UUID] = []
            for raw in raw_word_ids:
                try:
                    parsed_ids.append(UUID(str(raw)))
                except ValueError:
                    continue
            if parsed_ids:
                word_rows = {
                    row.id: row
                    for row in await self.db.scalars(
                        select(ContentItem).where(ContentItem.id.in_(parsed_ids))
                    )
                }
                for wid in parsed_ids:
                    row = word_rows.get(wid)
                    if row is not None:
                        words.append(
                            LinkedWordItem(
                                id=row.id,
                                title=row.title,
                                status=row.status,
                                cefr_level=row.cefr_level,
                                body=row.body,
                            )
                        )

        ai_review: AiReviewSummary | None = None
        if item.generation_batch_key:
            job = await self.db.scalar(
                select(AiJob)
                .where(
                    AiJob.job_type == "CONTENT_AUTHORING",
                    AiJob.generation_batch_key == item.generation_batch_key,
                    AiJob.parent_job_id.is_not(None),
                    AiJob.result_summary["lesson_id"].astext == str(item.id),
                )
                .limit(1)
            )
            if job is not None and isinstance(job.result_summary, dict):
                summary = job.result_summary
                ai_review = AiReviewSummary(
                    review_decision=summary.get("review_decision"),
                    review_scores=summary.get("review_scores"),
                    warnings=list(summary.get("warnings") or []),
                )

        base = _to_summary(item)
        return ContentItemDetail(
            **base.model_dump(),
            body=item.body,
            words=words,
            ai_review=ai_review,
        )

    async def apply_decision(
        self,
        admin_id: UUID,
        item_id: UUID,
        request: ReviewDecisionRequest,
    ) -> ContentItemDetail:
        try:
            item = await self.db.scalar(
                select(ContentItem).where(ContentItem.id == item_id).with_for_update()
            )
            if item is None:
                raise NotFoundError("Content item not found.")

            now = await self.db.scalar(select(func.now()))
            notes = (
                request.review_notes.strip()
                if request.review_notes and request.review_notes.strip()
                else None
            )

            linked_words: list[ContentItem] = []
            raw_word_ids = (item.body or {}).get("word_content_ids")
            if item.kind == "VOCABULARY_LESSON" and isinstance(raw_word_ids, list):
                parsed_ids: list[UUID] = []
                for raw in raw_word_ids:
                    try:
                        parsed_ids.append(UUID(str(raw)))
                    except ValueError:
                        continue
                if parsed_ids:
                    linked_words = list(
                        await self.db.scalars(
                            select(ContentItem)
                            .where(ContentItem.id.in_(parsed_ids))
                            .with_for_update()
                        )
                    )

            targets = [item, *linked_words]

            if request.action == "APPROVE":
                if item.status == "PUBLISHED":
                    raise ConflictError(
                        "Published items are immutable and cannot be moved back to REVIEW.",
                        code="CONTENT_ALREADY_PUBLISHED",
                    )
                for row in targets:
                    row.status = "REVIEW"
                    row.reviewed_by = admin_id
                    row.reviewed_at = now
                    if notes is not None:
                        row.review_notes = notes
            elif request.action == "REQUEST_CHANGES":
                if item.status == "PUBLISHED":
                    raise ConflictError(
                        "Published items are immutable and cannot be moved back to DRAFT.",
                        code="CONTENT_ALREADY_PUBLISHED",
                    )
                for row in targets:
                    row.status = "DRAFT"
                    row.reviewed_by = admin_id
                    row.reviewed_at = now
                    if notes is not None:
                        row.review_notes = notes
            elif request.action == "PUBLISH":
                if item.status == "ARCHIVED":
                    raise ConflictError(
                        "Archived items cannot be published directly.",
                        code="CONTENT_ARCHIVED",
                    )
                for row in targets:
                    row.status = "PUBLISHED"
                    row.reviewed_by = admin_id
                    row.reviewed_at = now
                    row.published_at = now
                    if notes is not None:
                        row.review_notes = notes
            elif request.action == "ARCHIVE":
                for row in targets:
                    row.status = "ARCHIVED"
                    row.reviewed_by = admin_id
                    row.reviewed_at = now
                    if notes is not None:
                        row.review_notes = notes

            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictError(
                "Another published core lesson already exists for this release and day.",
                code="PUBLISHED_SLOT_CONFLICT",
            ) from exc
        except Exception:
            await self.db.rollback()
            raise

        return await self.get_detail(item_id)
