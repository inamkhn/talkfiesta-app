from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from app.db.models.enums import (
    SpeakingExerciseType,
    SubmissionStatus,
    LiveSessionPersona,
    LiveSessionStatus,
    ReviewStatus
)


# ----------------------------------------
# AI Feedback Schemas
# ----------------------------------------
class GrammarCorrection(BaseModel):
    original: str
    corrected: str
    explanation: str

class VocabularySuggestion(BaseModel):
    word_used: str
    better_alternative: str
    reason: str

class SpeakingFeedback(BaseModel):
    fluency_feedback: str
    grammar_feedback: str
    vocabulary_feedback: str
    overall_strengths: str
    areas_for_improvement: str


# ----------------------------------------
# Speaking Exercise Schemas
# ----------------------------------------
class SpeakingExerciseBase(BaseModel):
    cycle: int
    day: int
    type: SpeakingExerciseType
    topic: str
    difficulty_level: str
    prompt_text: str
    target_duration_seconds: int
    instructions: Optional[str] = None
    target_cefr_level: str
    goal_tags: Dict[str, Any] = Field(default_factory=dict)
    
class SpeakingExerciseResponse(SpeakingExerciseBase):
    id: UUID
    review_status: ReviewStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------
# Speaking Submission Schemas
# ----------------------------------------
class SpeakingSubmissionCreate(BaseModel):
    exercise_id: UUID
    audio_url: str
    daily_activity_id: Optional[UUID] = None

class SpeakingSubmissionUpdate(BaseModel):
    status: Optional[SubmissionStatus] = None
    transcript: Optional[str] = None
    duration_seconds: Optional[int] = None
    word_count: Optional[int] = None
    words_per_minute: Optional[float] = None
    pause_count: Optional[int] = None
    filler_words_count: Optional[int] = None
    filler_words_list: Optional[Dict[str, int]] = None
    fluency_score: Optional[int] = None
    grammar_score: Optional[int] = None
    vocabulary_score: Optional[int] = None
    pronunciation_score: Optional[int] = None
    overall_score: Optional[int] = None
    grammar_corrections: Optional[List[GrammarCorrection]] = None
    vocabulary_suggestions: Optional[List[VocabularySuggestion]] = None
    ai_feedback: Optional[SpeakingFeedback] = None
    processing_job_id: Optional[str] = None
    completed_at: Optional[datetime] = None

class SpeakingSubmissionResponse(BaseModel):
    id: UUID
    user_id: UUID
    exercise_id: Optional[UUID] = None
    audio_url: str
    transcript: Optional[str] = None
    duration_seconds: Optional[int] = None
    word_count: Optional[int] = None
    words_per_minute: Optional[float] = None
    pause_count: Optional[int] = None
    filler_words_count: Optional[int] = None
    filler_words_list: Optional[Dict[str, int]] = None
    fluency_score: Optional[int] = None
    grammar_score: Optional[int] = None
    vocabulary_score: Optional[int] = None
    pronunciation_score: Optional[int] = None
    overall_score: Optional[int] = None
    grammar_corrections: Optional[List[GrammarCorrection]] = None
    vocabulary_suggestions: Optional[List[VocabularySuggestion]] = None
    ai_feedback: Optional[SpeakingFeedback] = None
    status: SubmissionStatus
    processing_job_id: Optional[str] = None
    submitted_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------
# Live Conversation Session Schemas
# ----------------------------------------
class LiveConversationSessionCreate(BaseModel):
    topic: str
    persona: LiveSessionPersona
    target_duration_seconds: int

class LiveSessionTranscriptTurn(BaseModel):
    speaker: str
    text: str
    timestamp_ms: int

class LiveConversationSessionEnd(BaseModel):
    actual_duration_seconds: int
    transcript: List[LiveSessionTranscriptTurn]

class LiveConversationSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    topic: str
    persona: LiveSessionPersona
    target_duration_seconds: int
    actual_duration_seconds: Optional[int] = None
    transcript_json: Optional[List[Dict[str, Any]]] = None
    turn_count: Optional[int] = None
    avg_response_time_seconds: Optional[float] = None
    avg_response_length_words: Optional[float] = None
    topic_relevance_score: Optional[int] = None
    status: LiveSessionStatus
    submission_id: Optional[UUID] = None
    ephemeral_token_issued_at: Optional[datetime] = None
    started_at: datetime
    ended_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class LiveConversationSessionTokenResponse(BaseModel):
    session_id: UUID
    ephemeral_token: str
    ws_endpoint: str

# ----------------------------------------
# Speaking Progress Schemas
# ----------------------------------------
class SpeakingProgressResponse(BaseModel):
    total_submissions: int
    average_overall_score: float
    average_fluency_score: float
    average_grammar_score: float
    average_vocabulary_score: float
