import uuid
from datetime import datetime
from sqlalchemy import Integer, ForeignKey, Enum as SQLEnum, func, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import (
    ContentGenerationModuleType,
    ContentGenerationStatus,
)


class ContentGenerationBatch(Base):
    __tablename__ = "content_generation_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    module_type: Mapped[ContentGenerationModuleType] = mapped_column(
        SQLEnum(ContentGenerationModuleType), nullable=False
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    total_slots: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[ContentGenerationStatus] = mapped_column(
        SQLEnum(ContentGenerationStatus), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
