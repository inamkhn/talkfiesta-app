import uuid
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

from app.db.models.enums import VocabWordStatus, SuggestionSourceType, SuggestionStatus


class WordCardResponse(BaseModel):
    id: uuid.UUID
    word: str
    definition: str
    part_of_speech: str
    difficulty_level: str
    pronunciation_ipa: Optional[str] = None
    pronunciation_audio_url: Optional[str] = None
    example_sentences: Any  # Usually list[str] or dict
    synonyms: List[str] = []
    antonyms: List[str] = []
    usage_tips: Optional[str] = None
    category: str
    target_cefr_level: str
    cycle: int
    day: int

    class Config:
        from_attributes = True


class ExerciseBankResponse(BaseModel):
    id: uuid.UUID
    word_id: uuid.UUID
    fill_blank_sentence: str
    fill_blank_correct_answer: str
    match_definition_distractor_1: str
    match_definition_distractor_2: str
    match_definition_distractor_3: str

    class Config:
        from_attributes = True


class WordWithExerciseResponse(BaseModel):
    word: WordCardResponse
    exercise: ExerciseBankResponse


class DayWordsResponse(BaseModel):
    cycle: int
    day: int
    words: List[WordWithExerciseResponse]


# Exercise Submission & Grading Schemas

class FillBlankSubmission(BaseModel):
    word_id: uuid.UUID
    user_answer: str


class FillBlankResult(BaseModel):
    word_id: uuid.UUID
    is_correct: bool
    correct_answer: str


class MatchPair(BaseModel):
    word_id: uuid.UUID
    selected_definition: str


class MatchSubmission(BaseModel):
    pairs: List[MatchPair]


class MatchPairResult(BaseModel):
    word_id: uuid.UUID
    is_correct: bool
    correct_definition: str


class MatchResult(BaseModel):
    pairs: List[MatchPairResult]
    score: int  # Number of correct matches (out of 5)


class ContextPair(BaseModel):
    word_id: uuid.UUID
    sentence: str = Field(..., min_length=5, max_length=500)


class ContextSubmission(BaseModel):
    submissions: List[ContextPair]


class ContextPairResult(BaseModel):
    word_id: uuid.UUID
    is_correct: bool
    feedback: str


class ContextResult(BaseModel):
    results: List[ContextPairResult]
    score: int  # Number of correct usages (out of 5)


class PronunciationSubmission(BaseModel):
    word_id: uuid.UUID
    audio_url: str  # URL to uploaded audio file


class PronunciationResult(BaseModel):
    word_id: uuid.UUID
    score: int  # Pronunciation confidence score (0-100)
    tip: Optional[str] = None  # Phonic/mouth position suggestion if score is low


# Session Finalization Schemas

class SessionCompleteRequest(BaseModel):
    day_number: int
    fill_blank_score: int = Field(..., ge=0, le=5)
    match_score: int = Field(..., ge=0, le=5)
    context_score: int = Field(..., ge=0, le=5)
    pronunciation_score: int = Field(..., ge=0, le=100)
    daily_activity_id: Optional[uuid.UUID] = None


class WordMasteryUpdate(BaseModel):
    word_id: uuid.UUID
    word: str
    previous_level: int
    new_level: int
    next_review_date: datetime


class SessionCompleteResponse(BaseModel):
    session_id: uuid.UUID
    overall_score: int  # Weighted score out of 100
    completed_at: datetime
    mastery_updates: List[WordMasteryUpdate]


# Spaced Repetition Review Queue Schemas

class ReviewQueueWord(BaseModel):
    user_vocab_id: uuid.UUID
    word: WordCardResponse
    exercise: ExerciseBankResponse
    mastery_level: int
    status: VocabWordStatus
    next_review_date: datetime


class ReviewQueueResponse(BaseModel):
    due_count: int
    words: List[ReviewQueueWord]


# Spaced Repetition Grading Submission

class ReviewWordSubmit(BaseModel):
    user_vocab_id: uuid.UUID
    is_correct: bool


class ReviewSubmission(BaseModel):
    reviews: List[ReviewWordSubmit]


class ReviewSubmissionResult(BaseModel):
    updated_words: List[WordMasteryUpdate]


# Personalized Suggestions Schemas

class PersonalSuggestionResponse(BaseModel):
    id: uuid.UUID
    source_type: SuggestionSourceType
    source_submission_id: Optional[uuid.UUID] = None
    original_word: str
    original_sentence: str
    suggested_word: str
    rewritten_sentence: str
    status: SuggestionStatus
    created_at: datetime

    class Config:
        from_attributes = True


# Paginated Word Bank Schemas

class UserVocabBankWord(BaseModel):
    id: uuid.UUID
    word: str
    definition: str
    part_of_speech: str
    category: str
    target_cefr_level: str
    mastery_level: int
    status: VocabWordStatus
    times_practiced: int
    times_reviewed: int
    next_review_date: datetime
    learned_at: datetime
    mastered_at: Optional[datetime] = None


class VocabBankResponse(BaseModel):
    total_count: int
    page: int
    per_page: int
    pages_count: int
    words: List[UserVocabBankWord]


class VocabStatsResponse(BaseModel):
    total_learned: int
    mastered_count: int
    learning_count: int
    reviewing_count: int
    review_due_count: int
