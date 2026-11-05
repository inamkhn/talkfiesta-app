"""Allowlisted learner-facing speaking lesson fields."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assessment.schemas import Cefr
from app.modules.speaking.feedback import SpeakingFeedback


class SpeakingActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: UUID
    kind: Literal["SPEAKING_LESSON"]
    title: str = Field(min_length=1)
    exercise_type: Literal["CONVERSATIONAL", "PUBLIC_SPEAKING", "IMPROMPTU"]
    topic: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    target_duration_seconds: int = Field(gt=0)
    target_cefr: Cefr
    preparation_seconds: int = Field(ge=0)
    tips: list[str]


class SpeakingTodayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    module: Literal["SPEAKING"] = "SPEAKING"
    plan_id: UUID
    module_progress_id: UUID
    cycle: int = Field(ge=1, le=5)
    day: int = Field(ge=1, le=21)
    module_status: Literal["ACTIVE", "COMPLETED"]
    activity: SpeakingActivity | None
    existing_draft_id: UUID | None = None


class CreateSpeakingDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_item_id: UUID


class SpeakingDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    submission_id: UUID
    mode: Literal["RECORDED_SPEAKING"]
    status: Literal["DRAFT"]
    evaluation_status: Literal["NOT_REQUIRED"]
    content_item_id: UUID
    media_upload_id: UUID | None
    created_at: datetime


class SubmitSpeakingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_upload_id: UUID


class SubmitSpeakingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    submission_id: UUID
    activity_status: Literal["COMPLETED"] = "COMPLETED"
    evaluation_status: Literal["PENDING"] = "PENDING"
    job_id: UUID
    credited_day: int = Field(ge=1, le=21)
    next_speaking_day: int | None = Field(default=None, ge=1, le=21)
    submission_url: str


class SpeakingEvaluationError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: Literal["SPEAKING_EVALUATION_FAILED"] = "SPEAKING_EVALUATION_FAILED"
    message: str = "Feedback could not be completed. Your activity credit is preserved."
    retry_allowed: Literal[False] = False


class SpeakingEvaluationProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["NOT_REQUIRED", "PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    stage: Literal[
        "NOT_STARTED",
        "WAITING_FOR_WORKER",
        "TRANSCRIBING_AUDIO",
        "EVALUATING_LANGUAGE",
        "SAVING_RESULTS",
        "RETRY_SCHEDULED",
        "DONE",
        "FAILED",
    ]
    retry_after_seconds: int | None = None
    rubric_version: str | None = None
    error: SpeakingEvaluationError | None = None


class SpeakingSubmissionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    submission_id: UUID
    content_item_id: UUID
    activity_status: Literal["IN_PROGRESS", "COMPLETED", "REJECTED"]
    evaluation: SpeakingEvaluationProgress
    transcript: str | None = Field(default=None, max_length=20000)
    feedback: SpeakingFeedback | None = None


SpeakingEvaluationStatus = Literal[
    "NOT_REQUIRED", "PENDING", "PROCESSING", "COMPLETED", "FAILED"
]


class SpeakingHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    submission_id: UUID
    content_item_id: UUID
    title: str
    submitted_at: datetime | None
    activity_status: Literal["IN_PROGRESS", "COMPLETED", "REJECTED"]
    evaluation_status: SpeakingEvaluationStatus
    grammar_score: int | None = Field(default=None, ge=0, le=100)


class SpeakingHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    items: list[SpeakingHistoryItem] = Field(max_length=100)
    next_cursor: str | None = None
