"""Central content bank (`content_items`) for questions, lessons, words and interview items."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base

CONTENT_KINDS = (
    "ASSESSMENT_QUESTION",
    "SPEAKING_LESSON",
    "VOCABULARY_LESSON",
    "WRITING_LESSON",
    "VOCAB_WORD",
    "INTERVIEW_QUESTION",
    "LIVE_TOPIC",
)


class ContentItem(Base):
    """A versioned, immutable-once-published item in the unified content bank."""

    __tablename__ = "content_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('ASSESSMENT_QUESTION','SPEAKING_LESSON','VOCABULARY_LESSON',"
            "'WRITING_LESSON','VOCAB_WORD','INTERVIEW_QUESTION','LIVE_TOPIC')",
            name="valid_content_kind",
        ),
        CheckConstraint(
            "status IN ('DRAFT','REVIEW','PUBLISHED','ARCHIVED')",
            name="valid_content_status",
        ),
        CheckConstraint(
            "origin IN ('HUMAN','AI')",
            name="valid_content_origin",
        ),
        CheckConstraint(
            "cycle IS NULL OR cycle BETWEEN 1 AND 5",
            name="valid_content_cycle",
        ),
        CheckConstraint(
            "day IS NULL OR day BETWEEN 1 AND 21",
            name="valid_content_day",
        ),
        CheckConstraint(
            "content_version >= 1",
            name="valid_content_version",
        ),
        Index(
            "ix_content_items_lookup",
            "kind",
            "status",
            "release_key",
            "cefr_level",
            "goal_variant",
        ),
        Index(
            "ix_content_items_curriculum",
            "release_key",
            "module",
            "cycle",
            "day",
            "goal_variant",
            "slot",
        ),
        Index(
            "ix_content_items_interview",
            "kind",
            "domain",
            "agent_type",
        ),
        Index(
            "uq_published_core_lesson",
            "release_key",
            "module",
            "cycle",
            "day",
            "cefr_level",
            "goal_variant",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED' AND slot = 'CORE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    module: Mapped[str | None] = mapped_column(String(20), nullable=True)
    release_key: Mapped[str] = mapped_column(String(60), nullable=False)
    cycle: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cefr_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    goal_variant: Mapped[str | None] = mapped_column(String(40), nullable=True)
    slot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(40), nullable=True)
    agent_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="HUMAN")
    generation_batch_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

