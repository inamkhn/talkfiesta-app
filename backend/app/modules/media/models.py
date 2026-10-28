"""Uploaded audio metadata.

Rows are created before the object is confirmed, so ``status`` tracks the
lifecycle and the verified duration is stored separately from the
client-reported value.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class MediaUpload(Base):
    """A private object-store recording bound to an attempt and item."""

    __tablename__ = "media_uploads"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_media_uploads_object_key"),
        Index("ix_media_uploads_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified_duration_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="INITIATED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
