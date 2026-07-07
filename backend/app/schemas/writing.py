import uuid
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

from app.db.models.enums import WritingPromptType, SubmissionStatus


class WritingPromptResponse(BaseModel):
    id: uuid.UUID
    cycle: int
    day: int
    type: WritingPromptType
    difficulty_level: str
    prompt_title: str
    prompt_text: str
    target_word_count: int
    time_limit_minutes: Optional[int] = None
    focus_areas: Any = []
    writing_tips: Optional[str] = None
    sample_outline: Optional[str] = None
    sensitivity_flagged: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DraftSaveRequest(BaseModel):
    prompt_id: uuid.UUID
    content: str


class DraftSaveResponse(BaseModel):
    submission_id: uuid.UUID
    status: SubmissionStatus
    last_edited_at: datetime


class SubmissionCreateRequest(BaseModel):
    prompt_id: uuid.UUID
    content: str
    word_count: int
    time_spent_seconds: Optional[int] = None


class SubmissionReviseRequest(BaseModel):
    content: str
    word_count: int
    time_spent_seconds: Optional[int] = None


class WritingSubmissionVersionResponse(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    version_number: int
    text_content: str
    grammar_score: Optional[int] = None
    structure_score: Optional[int] = None
    vocabulary_score: Optional[int] = None
    coherence_score: Optional[int] = None
    overall_score: Optional[int] = None
    ai_feedback: Optional[Any] = None
    fixed_issues: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WritingSubmissionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    prompt_id: uuid.UUID
    daily_activity_id: Optional[uuid.UUID] = None
    revision_count: int
    word_count: Optional[int] = None
    time_spent_seconds: Optional[int] = None
    grammar_score: Optional[int] = None
    structure_score: Optional[int] = None
    vocabulary_score: Optional[int] = None
    coherence_score: Optional[int] = None
    overall_score: Optional[int] = None
    status: SubmissionStatus
    processing_job_id: Optional[str] = None
    submitted_at: datetime
    completed_at: Optional[datetime] = None
    versions: List[WritingSubmissionVersionResponse] = []

    class Config:
        from_attributes = True


class WritingPortfolioResponse(BaseModel):
    submissions: List[WritingSubmissionResponse]
