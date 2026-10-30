"""Per-word mastery, spaced repetition and personalized suggestions (`user_vocabulary`)."""

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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class UserVocabulary(Base):
    """Per-user vocabulary state for curriculum words and mistake-driven suggestions."""

    __tablename__ = "user_vocabulary"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "word_key", name="uq_user_vocabulary_word_key"
        ),
        CheckConstraint(
            "status IN ('SUGGESTED','LEARNING','REVIEWING','MASTERED','DISMISSED')",
            name="valid_user_vocab_status",
        ),
        CheckConstraint(
            "mastery_level BETWEEN 1 AND 5",
            name="valid_user_vocab_mastery",
        ),
        Index("ix_user_vocabulary_due_review", "user_id", "next_review_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    word_content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    word_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="LEARNING"
    )
    mastery_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
    review_interval_days: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    times_practiced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    learned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mastered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

