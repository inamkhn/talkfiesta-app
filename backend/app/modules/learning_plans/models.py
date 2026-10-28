"""Learning plans, module enrollments and activity completion credits."""

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
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class LearningPlan(Base):
    """An active 21-day plan created from a finalised assessment result.

    ``assessment_result_id`` is unique, so a result can only ever produce one
    plan; later cycles require a new assessment result.
    """

    __tablename__ = "learning_plans"
    __table_args__ = (
        UniqueConstraint(
            "assessment_result_id", name="uq_learning_plans_assessment_result_id"
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
    assessment_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_results.id"),
        nullable=False,
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    placement_cefr: Mapped[str] = mapped_column(String(2), nullable=False)
    primary_goal: Mapped[str] = mapped_column(String(40), nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModuleEnrollment(Base):
    """Per-module progress inside a plan.

    ``current_day`` is the next uncompleted required day, not today's date.
    ``curriculum_version_id`` stays nullable so a learner can be enrolled
    before suitable published content exists.
    """

    __tablename__ = "module_enrollments"
    __table_args__ = (
        CheckConstraint(
            "current_day BETWEEN 1 AND 21",
            name="ck_module_enrollments_valid_enrollment_day",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','AWAITING_CONTENT')",
            name="ck_module_enrollments_valid_enrollment_status",
        ),
        UniqueConstraint("learning_plan_id", "module", name="uq_plan_module"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learning_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    curriculum_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    module: Mapped[str] = mapped_column(String(20), nullable=False)
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prioritized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="AWAITING_CONTENT"
    )


class ActivityCompletion(Base):
    """Immutable credit for a completed activity.

    Evidence is referenced polymorphically through ``source_type``/``source_id``
    rather than typed foreign keys, so the service layer must validate it.
    """

    __tablename__ = "activity_completions"
    __table_args__ = (
        UniqueConstraint(
            "enrollment_id", "activity_id", name="uq_enrollment_activity_completion"
        ),
        UniqueConstraint(
            "source_type", "source_id", name="uq_activity_completion_source"
        ),
        Index("ix_completion_enrollment_date", "enrollment_id", "local_practice_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("module_enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_activities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    local_practice_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
