"""Durable AI jobs (`ai_jobs`) and transactional outbox events (`outbox_events`) (V4)."""

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


class AiJob(Base):
    """Async OpenAI/LangGraph evaluation or authoring job with tracing and retry state."""

    __tablename__ = "ai_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_jobs_idempotency_key"),
        CheckConstraint(
            "job_type IN ('TRANSCRIBE','ASSESSMENT','SPEAKING_FEEDBACK',"
            "'WRITING_FEEDBACK','VOCAB_CONTEXT','CONTENT_AUTHORING','SESSION_FEEDBACK')",
            name="valid_ai_job_type",
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','RETRYABLE','FAILED')",
            name="valid_ai_job_status",
        ),
        Index("ix_ai_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    assessment_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=True,
    )
    practice_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_submissions.id", ondelete="CASCADE"),
        nullable=True,
    )
    practice_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rubric_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    langsmith_run_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OutboxEvent(Base):
    """Queued message written in the same transaction as the state change."""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index(
            "ix_outbox_unpublished",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
