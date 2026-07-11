import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, Enum as SQLEnum, func, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    SpeakingExerciseType,
    ContentSource,
    ReviewStatus,
    SubmissionStatus,
    LiveSessionPersona,
    LiveSessionStatus,
)

import os
from sqlalchemy.dialects.postgresql import JSONB

USE_PGVECTOR = os.getenv("USE_PGVECTOR", "false").lower() == "true"

Vector = None
if USE_PGVECTOR:
    try:
        from pgvector.sqlalchemy import Vector  # type: ignore
    except ImportError:
        pass

if Vector is None:
    class Vector(JSONB):
        def __init__(self, dim=None, *args, **kwargs):
            super().__init__(*args, **kwargs)


class SpeakingExercise(Base):
    __tablename__ = "speaking_exercises"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[SpeakingExerciseType] = mapped_column(
        SQLEnum(SpeakingExerciseType), nullable=False
    )
    topic: Mapped[str] = mapped_column(String, nullable=False)
    difficulty_level: Mapped[str] = mapped_column(String, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_cefr_level: Mapped[str] = mapped_column(String, nullable=False)
    goal_tags: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    topic_embedding: Mapped[list | None] = mapped_column(Vector(768), nullable=True)
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

    submissions = relationship("SpeakingSubmission", back_populates="exercise")


class SpeakingSubmission(Base):
    __tablename__ = "speaking_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    exercise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speaking_exercises.id"), nullable=True
    )
    daily_activity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_progress.id"), nullable=True
    )
    audio_url: Mapped[str] = mapped_column(String, nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    words_per_minute: Mapped[float | None] = mapped_column(Float, nullable=True)
    pause_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filler_words_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filler_words_list: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fluency_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grammar_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vocabulary_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pronunciation_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grammar_corrections: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    vocabulary_suggestions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
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

    exercise = relationship("SpeakingExercise", back_populates="submissions")
    live_sessions = relationship("LiveConversationSession", back_populates="submission")


class LiveConversationSession(Base):
    __tablename__ = "live_conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    topic: Mapped[str] = mapped_column(String, nullable=False)
    persona: Mapped[LiveSessionPersona] = mapped_column(
        SQLEnum(LiveSessionPersona), nullable=False
    )
    target_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    turn_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_response_time_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    avg_response_length_words: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    topic_relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[LiveSessionStatus] = mapped_column(
        SQLEnum(LiveSessionStatus), default=LiveSessionStatus.ACTIVE, nullable=False
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("speaking_submissions.id"), nullable=True
    )
    ephemeral_token_issued_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    submission = relationship("SpeakingSubmission", back_populates="live_sessions")
