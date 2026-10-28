"""Curriculum versions and their daily activities."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class CurriculumVersion(Base):
    """An immutable-once-published version of one module at one CEFR band."""

    __tablename__ = "curriculum_versions"
    __table_args__ = (
        CheckConstraint(
            "version_number >= 1",
            name="ck_curriculum_versions_valid_curriculum_version_number",
        ),
        CheckConstraint(
            "cycle_number BETWEEN 1 AND 5",
            name="ck_curriculum_versions_valid_curriculum_cycle",
        ),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','ARCHIVED')",
            name="ck_curriculum_versions_valid_curriculum_status",
        ),
        UniqueConstraint(
            "cycle_number",
            "module",
            "cefr_level",
            "goal_variant",
            "version_number",
            name="uq_curriculum_version_identity",
        ),
        Index(
            "ix_curriculum_lookup",
            "cycle_number",
            "module",
            "cefr_level",
            "goal_variant",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    module: Mapped[str] = mapped_column(String(20), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(2), nullable=False)
    goal_variant: Mapped[str] = mapped_column(String(40), nullable=False, default="GENERAL")
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="HUMAN")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CurriculumActivity(Base):
    """One day of content for a curriculum version.

    Content is held in a single JSON payload; there are no typed foreign keys
    to speaking, writing or vocabulary content tables yet.
    """

    __tablename__ = "curriculum_activities"
    __table_args__ = (
        CheckConstraint(
            "day BETWEEN 1 AND 21",
            name="ck_curriculum_activities_valid_curriculum_day",
        ),
        CheckConstraint(
            "estimated_minutes BETWEEN 1 AND 90",
            name="ck_curriculum_activities_valid_curriculum_minutes",
        ),
        UniqueConstraint(
            "curriculum_version_id", "day", name="uq_curriculum_version_day"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    topic: Mapped[str] = mapped_column(String(80), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
