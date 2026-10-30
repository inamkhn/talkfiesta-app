"""Awarded learner badges (`user_achievements`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class UserAchievement(Base):
    """An achievement badge unlocked by a learner; badge definitions live in code."""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "achievement_key", name="uq_user_achievement_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    achievement_key: Mapped[str] = mapped_column(String(60), nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

