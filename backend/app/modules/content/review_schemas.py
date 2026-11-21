"""Pydantic schemas for Admin Content Review and editorial decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContentItemSummary(BaseModel):
    id: UUID
    kind: str
    module: str | None
    release_key: str
    cycle: int | None
    day: int | None
    cefr_level: str | None
    goal_variant: str | None
    title: str
    status: str
    origin: str
    generation_batch_key: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    published_at: datetime | None


class LinkedWordItem(BaseModel):
    id: UUID
    title: str
    status: str
    cefr_level: str | None
    body: dict[str, Any]


class AiReviewSummary(BaseModel):
    review_decision: str | None = None
    review_scores: dict[str, int] | None = None
    warnings: list[str] = Field(default_factory=list)


class ContentItemDetail(ContentItemSummary):
    body: dict[str, Any]
    words: list[LinkedWordItem] = Field(default_factory=list)
    ai_review: AiReviewSummary | None = None


class ContentItemListResponse(BaseModel):
    items: list[ContentItemSummary]
    total: int


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["APPROVE", "REQUEST_CHANGES", "PUBLISH", "ARCHIVE"]
    review_notes: str | None = Field(default=None, max_length=2000)
