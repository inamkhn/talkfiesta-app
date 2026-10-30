"""Owner-scoped private audio uploads (`media_uploads`)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class MediaUpload(Base):
    """A private object-store audio record verified before AI evaluation."""

    __tablename__ = "media_uploads"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_media_uploads_object_key"),
        CheckConstraint(
            "purpose IN ('ASSESSMENT','SPEAKING','PRONUNCIATION','INTERVIEW')",
            name="valid_media_purpose",
        ),
        CheckConstraint(
            "status IN ('INITIATED','VERIFIED','REJECTED','DELETED')",
            name="valid_media_status",
        ),
        Index("ix_media_uploads_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="INITIATED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delete_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
