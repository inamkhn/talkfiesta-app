"""Assessment question bank, attempts, items, responses and results."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base

# Statuses that keep an initial attempt 'active' for the partial unique index.
_ACTIVE_ATTEMPT_STATUSES = (
    "'CREATED','IN_PROGRESS','SUBMITTED','PROCESSING','FAILED_RETRYABLE'"
)


class AssessmentQuestion(Base):
    """A question in the versioned assessment bank.

    The correct answer is stored inline (``correct_choice_id``); questions are
    treated as immutable once published so learner-visible payloads stay
    stable.
    """

    __tablename__ = "assessment_questions"
    __table_args__ = (
        UniqueConstraint(
            "version", "position", name="uq_assessment_question_version_position"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="starter-v1"
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    skill: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_choice_id: Mapped[str | None] = mapped_column(String(5), nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AssessmentAttempt(Base):
    """One learner sitting of the assessment."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (
        Index("ix_assessment_attempts_user_id", "user_id"),
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
    question_bank_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="starter-v1"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AssessmentItem(Base):
    """A question assigned at a specific position within an attempt."""

    __tablename__ = "assessment_items"
    __table_args__ = (
        UniqueConstraint("attempt_id", "position", name="uq_attempt_item_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_questions.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class AssessmentResponse(Base):
    """Autosaved answer for one assigned item.

    ``version`` supports idempotent autosave; ``media_upload_id`` links a
    spoken answer to the uploaded recording.
    """

    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_assessment_responses_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    selected_choice_id: Mapped[str | None] = mapped_column(String(5), nullable=True)
    text_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    media_upload_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_uploads.id"), nullable=True
    )
    speaking_skipped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AssessmentResult(Base):
    """Finalised placement outcome for one attempt."""

    __tablename__ = "assessment_results"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_assessment_results_attempt_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    placement_cefr: Mapped[str | None] = mapped_column(String(2), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rubric_version: Mapped[str] = mapped_column(String(40), nullable=False)
    skill_evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
