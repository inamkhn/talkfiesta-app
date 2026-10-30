"""Practice submissions (speaking, writing, vocabulary) and live/interview practice sessions (V4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class PracticeSubmission(Base):
    """A recorded speaking answer, writing draft/revision, or vocabulary quiz/review."""

    __tablename__ = "practice_submissions"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('RECORDED_SPEAKING','WRITING','VOCAB_QUIZ','VOCAB_REVIEW','PRONUNCIATION')",
            name="valid_submission_mode",
        ),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','ACCEPTED','REJECTED')",
            name="valid_submission_status",
        ),
        CheckConstraint(
            "evaluation_status IN ('NOT_REQUIRED','PENDING','PROCESSING','COMPLETED','FAILED')",
            name="valid_submission_eval_status",
        ),
        CheckConstraint(
            "revision_number BETWEEN 1 AND 4",
            name="valid_submission_revision_number",
        ),
        Index("ix_practice_submissions_user_created", "user_id", "created_at"),
        Index(
            "uq_submission_revision_group",
            "revision_group_id",
            "revision_number",
            unique=True,
            postgresql_where=text("revision_group_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module_progress_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("module_progress.id", ondelete="SET NULL"),
        nullable=True,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SUBMITTED"
    )
    evaluation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    media_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_uploads.id", ondelete="SET NULL"),
        nullable=True,
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    revision_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    revision_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PracticeSession(Base):
    """An interactive AI voice conversation, mock interview, or multi-agent interview panel."""

    __tablename__ = "practice_sessions"
    __table_args__ = (
        CheckConstraint(
            "session_type IN ('LIVE_CONVERSATION','MOCK_INTERVIEW','INTERVIEW_PANEL')",
            name="valid_practice_session_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','ENDED','ABANDONED','ERROR')",
            name="valid_practice_session_status",
        ),
        Index(
            "ix_practice_sessions_user_started",
            "user_id",
            "started_at",
            "session_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    transcript: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

