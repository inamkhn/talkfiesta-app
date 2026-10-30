"""Learning plans, per-module progress and durable activity completions (V4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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


class LearningPlan(Base):
    """A 21-day cycle plan owned by a learner."""

    __tablename__ = "learning_plans"
    __table_args__ = (
        CheckConstraint("cycle BETWEEN 1 AND 5", name="valid_plan_cycle"),
        CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','PAUSED','SUPERSEDED')",
            name="valid_plan_status",
        ),
        Index(
            "uq_one_active_plan",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="SET NULL"),
        nullable=True,
    )
    cycle: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    placement_cefr: Mapped[str] = mapped_column(String(2), nullable=False)
    plan_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ModuleProgress(Base):
    """Independent Speaking/Vocabulary/Writing day position within a learning plan."""

    __tablename__ = "module_progress"
    __table_args__ = (
        UniqueConstraint(
            "learning_plan_id", "module", name="uq_plan_module_progress"
        ),
        CheckConstraint(
            "module IN ('SPEAKING','VOCABULARY','WRITING')",
            name="valid_progress_module",
        ),
        CheckConstraint(
            "current_day BETWEEN 1 AND 21",
            name="valid_progress_day",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','AWAITING_CONTENT','COMPLETED')",
            name="valid_progress_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learning_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    module: Mapped[str] = mapped_column(String(20), nullable=False)
    content_release: Mapped[str] = mapped_column(String(60), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(2), nullable=False)
    goal_variant: Mapped[str] = mapped_column(
        String(40), nullable=False, default="GENERAL"
    )
    current_day: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="AWAITING_CONTENT"
    )
    prioritized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ActivityCompletion(Base):
    """Immutable credit for a completed curriculum activity, driving streaks and progress."""

    __tablename__ = "activity_completions"
    __table_args__ = (
        UniqueConstraint(
            "module_progress_id",
            "content_item_id",
            name="uq_module_progress_content_completion",
        ),
        UniqueConstraint(
            "source_submission_id", name="uq_activity_completion_submission"
        ),
        UniqueConstraint(
            "source_session_id", name="uq_activity_completion_session"
        ),
        CheckConstraint(
            "(source_submission_id IS NOT NULL AND source_session_id IS NULL) OR "
            "(source_submission_id IS NULL AND source_session_id IS NOT NULL)",
            name="exactly_one_completion_source",
        ),
        Index(
            "ix_activity_completions_user_date", "user_id", "local_practice_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module_progress_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("module_progress.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_submissions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_sessions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    local_practice_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

