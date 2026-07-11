import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, func, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    WritingPromptType,
    ContentSource,
    ReviewStatus,
    SubmissionStatus,
)


class WritingPrompt(Base):
    __tablename__ = "writing_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[WritingPromptType] = mapped_column(
        SQLEnum(WritingPromptType), nullable=False
    )
    difficulty_level: Mapped[str] = mapped_column(String, nullable=False)
    prompt_title: Mapped[str] = mapped_column(String, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    focus_areas: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    writing_tips: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_outline: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitivity_flagged: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    generated_by: Mapped[ContentSource] = mapped_column(
        SQLEnum(ContentSource), nullable=False
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus), nullable=False
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    generation_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_generation_batches.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    submissions = relationship("WritingSubmission", back_populates="prompt")


class WritingSubmission(Base):
    __tablename__ = "writing_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("writing_prompts.id"), nullable=False
    )
    daily_activity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_progress.id"), nullable=True
    )
    revision_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grammar_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structure_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocabulary_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coherence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        SQLEnum(SubmissionStatus), default=SubmissionStatus.PENDING, nullable=False
    )
    processing_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    prompt = relationship("WritingPrompt", back_populates="submissions")
    versions = relationship(
        "WritingSubmissionVersion",
        back_populates="submission",
        cascade="all, delete-orphan",
    )


class WritingSubmissionVersion(Base):
    __tablename__ = "writing_submission_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("writing_submissions.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    grammar_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structure_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocabulary_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coherence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fixed_issues: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    submission = relationship("WritingSubmission", back_populates="versions")
