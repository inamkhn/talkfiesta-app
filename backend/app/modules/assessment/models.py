"""Assessment attempts and assigned/answered assessment responses (V4)."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base

_ACTIVE_ATTEMPT_STATUSES = (
    "'IN_PROGRESS','SUBMITTED','PROCESSING','FAILED_RETRYABLE'"
)


class AssessmentAttempt(Base):
    """One learner sitting of the assessment, including its provisional CEFR result."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('INITIAL','REASSESSMENT')",
            name="valid_attempt_kind",
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS','SUBMITTED','PROCESSING','COMPLETED','FAILED_RETRYABLE','FAILED_FINAL')",
            name="valid_attempt_status",
        ),
        Index("ix_assessment_attempts_user_started", "user_id", "started_at"),
        Index(
            "uq_active_initial_attempt",
            "user_id",
            unique=True,
            postgresql_where=text(
                f"kind = 'INITIAL' AND status IN ({_ACTIVE_ATTEMPT_STATUSES})"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="INITIAL")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="IN_PROGRESS"
    )
    content_release: Mapped[str] = mapped_column(
        String(60), nullable=False, default="starter-v1"
    )
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    placement_cefr: Mapped[str | None] = mapped_column(String(2), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AssessmentResponse(Base):
    """An assigned question slot and the learner's response within an attempt.

    An ``ASSIGNED`` row is created when the question is selected, removing the
    need for a separate ``assessment_items`` join table.
    """

    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint(
            "assessment_attempt_id",
            "position",
            name="uq_assessment_response_attempt_position",
        ),
        UniqueConstraint(
            "assessment_attempt_id",
            "question_content_id",
            name="uq_assessment_response_attempt_question",
        ),
        CheckConstraint(
            "status IN ('ASSIGNED','ANSWERED','SKIPPED')",
            name="valid_assessment_response_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assessment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ASSIGNED"
    )
    answer: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    media_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("media_uploads.id", ondelete="SET NULL"),
        nullable=True,
    )
    grading: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
