import uuid
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

from app.db.models.enums import WritingPromptType, SubmissionStatus


class GrammarIssue(BaseModel):
    type: Optional[str] = None
    original_text: str
    replacement_text: str
    explanation: str

class GrammarReport(BaseModel):
    score: int
    issues: List[GrammarIssue]

class StructureReport(BaseModel):
    score: int
    notes: List[str]
    suggestions: List[str]

class VocabularySuggestion(BaseModel):
    original_word: str
    suggested_word: str
    context: str
    explanation: str

class VocabularyReport(BaseModel):
    score: int
    suggestions: List[VocabularySuggestion]

class CoherenceReport(BaseModel):
    score: int
    notes: List[str]
    topic_relevance: str

class SupervisorReport(BaseModel):
    overall_score: int
    grammar_score: int
    structure_score: int
    vocabulary_score: int
    coherence_score: int
    strengths: List[str]
    improvements: List[str]
    actionable_tips: List[str]
    narrative_summary: str

class AIFeedbackSchema(BaseModel):
    grammar: Optional[GrammarReport] = None
    structure: Optional[StructureReport] = None
    vocabulary: Optional[VocabularyReport] = None
    coherence: Optional[CoherenceReport] = None
    supervisor: Optional[SupervisorReport] = None

class FixedIssue(BaseModel):
    description: str
    original_text: str

class FixedIssuesSchema(BaseModel):
    fixed_issues: List[FixedIssue] = []
    still_present_issues: List[FixedIssue] = []
    new_issues_introduced: List[FixedIssue] = []
    error: Optional[str] = None



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
    ai_feedback: Optional[AIFeedbackSchema] = None
    fixed_issues: Optional[FixedIssuesSchema] = None
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
