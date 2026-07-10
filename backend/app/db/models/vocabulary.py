import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, func, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    ContentSource,
    ReviewStatus,
    VocabWordStatus,
    SuggestionSourceType,
    SuggestionStatus,
)




class VocabularyWord(Base):
    __tablename__ = "vocabulary_words"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    word: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    part_of_speech: Mapped[str] = mapped_column(String, nullable=False)
    difficulty_level: Mapped[str] = mapped_column(String, nullable=False)
    pronunciation_ipa: Mapped[str | None] = mapped_column(String, nullable=True)
    pronunciation_audio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    example_sentences: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synonyms: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    antonyms: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    usage_tips: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    target_cefr_level: Mapped[str] = mapped_column(String, nullable=False)
    cycle: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)

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

    exercises = relationship("VocabularyExerciseBank", back_populates="word")
    user_associations = relationship("UserVocabulary", back_populates="word")


class VocabularyExerciseBank(Base):
    __tablename__ = "vocabulary_exercise_bank"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    word_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vocabulary_words.id"), nullable=False
    )
    fill_blank_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    fill_blank_correct_answer: Mapped[str] = mapped_column(String, nullable=False)
    match_definition_distractor_1: Mapped[str] = mapped_column(Text, nullable=False)
    match_definition_distractor_2: Mapped[str] = mapped_column(Text, nullable=False)
    match_definition_distractor_3: Mapped[str] = mapped_column(Text, nullable=False)

    word = relationship("VocabularyWord", back_populates="exercises")


class UserVocabulary(Base):
    __tablename__ = "user_vocabulary"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    word_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vocabulary_words.id"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    mastery_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[VocabWordStatus] = mapped_column(
        SQLEnum(VocabWordStatus), default=VocabWordStatus.LEARNING, nullable=False
    )
    times_practiced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_reviewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    next_review_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    learned_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    word = relationship("VocabularyWord", back_populates="user_associations")


class VocabularyPracticeSession(Base):
    __tablename__ = "vocabulary_practice_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    daily_activity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daily_progress.id"), nullable=True
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    fill_blank_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pronunciation_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )


class PersonalizedVocabSuggestion(Base):
    __tablename__ = "personalized_vocab_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    source_type: Mapped[SuggestionSourceType] = mapped_column(
        SQLEnum(SuggestionSourceType), nullable=False
    )
    source_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    original_word: Mapped[str] = mapped_column(String, nullable=False)
    original_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_word: Mapped[str] = mapped_column(String, nullable=False)
    rewritten_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus), default=SuggestionStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
