"""Onboarding state and learning preferences."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class UserLearningPreference(Base):
    """Multi-goal preferences captured during onboarding."""

    __tablename__ = "user_learning_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    goals: Mapped[list] = mapped_column(JSON, nullable=False)
    focus_areas: Mapped[list] = mapped_column(JSON, nullable=False)
    topics: Mapped[list] = mapped_column(JSON, nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    self_reported_comfort: Mapped[str] = mapped_column(String(25), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OnboardingSession(Base):
    """Resumable onboarding state.

    ``user_id`` is unique across every status, so this table holds one current
    row per user rather than a historical series.
    """

    __tablename__ = "onboarding_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_onboarding_sessions_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="NOT_STARTED"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
