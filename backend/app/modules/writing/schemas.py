"""Pydantic contracts for the Writing module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

WritingType = Literal["DESCRIPTIVE", "NARRATIVE", "ARGUMENTATIVE", "OPINION"]
WritingEvaluationStatus = Literal[
    "NOT_REQUIRED", "PENDING", "PROCESSING", "COMPLETED", "FAILED"
]


class WritingPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: Literal["WRITING_LESSON"] = "WRITING_LESSON"
    title: str = Field(min_length=1, max_length=200)
    writing_type: WritingType
    instructions: str = Field(min_length=1, max_length=2000)
    target_word_count: int = Field(ge=10, le=2000, strict=True)
    minimum_word_count: int = Field(ge=10, le=2000, strict=True)
    maximum_word_count: int = Field(ge=10, le=5000, strict=True)
    time_limit_minutes: int | None = Field(default=None, ge=1, le=240, strict=True)
    tips: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_word_count_bounds(self):
        if not (
            self.minimum_word_count
            <= self.target_word_count
            <= self.maximum_word_count
        ):
            raise ValueError(
                "Word count bounds must satisfy minimum_word_count <= target_word_count <= maximum_word_count."
            )
        return self


class WritingTodayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["WRITING"] = "WRITING"
    cycle: int = Field(ge=1)
    day: int = Field(ge=1, le=21)
    module_progress_id: UUID
    module_status: Literal["ACTIVE", "COMPLETED"]
    prompt: WritingPrompt | None = None
    existing_draft_id: UUID | None = None


class CreateWritingSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_item_id: UUID


class WritingDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    revision_group_id: UUID
    revision_number: int = Field(ge=1, le=4)
    status: Literal["DRAFT"] = "DRAFT"
    edit_version: int = Field(ge=0)
    text: str
    word_count: int = Field(ge=0)


class SaveWritingDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_edit_version: int = Field(ge=0, strict=True)
    text: str = Field(max_length=25000)


class SaveWritingDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: Literal["DRAFT"] = "DRAFT"
    edit_version: int = Field(ge=0)
    word_count: int = Field(ge=0)
    saved_at: datetime


class SubmitWritingSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=25000)


class SubmitWritingSubmissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    revision_group_id: UUID
    revision_number: int = Field(ge=1, le=4)
    activity_status: Literal["COMPLETED"] = "COMPLETED"
    evaluation_status: WritingEvaluationStatus = "PENDING"
    job_id: UUID
    feedback_url: str = Field(min_length=1, max_length=256)
    next_module_day: int | None = Field(default=None, ge=1, le=21)


class WritingCorrectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original: str = Field(min_length=1, max_length=1000)
    suggestion: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=1000)


class WritingRubricScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grammar: int = Field(ge=0, le=100)
    structure: int = Field(ge=0, le=100)
    vocabulary: int = Field(ge=0, le=100)
    coherence: int = Field(ge=0, le=100)
    overall: int = Field(ge=0, le=100)


class WritingRevisionComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixed_issues: list[str] = Field(default_factory=list, max_length=20)
    remaining_issues: list[str] = Field(default_factory=list, max_length=20)
    new_issues: list[str] = Field(default_factory=list, max_length=20)


class WritingFeedbackReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_version: str = Field(
        default="writing-rubric-v1", min_length=1, max_length=64
    )
    scores: WritingRubricScores
    corrections: list[WritingCorrectionItem] = Field(
        default_factory=list, max_length=50
    )
    strengths: list[str] = Field(default_factory=list, max_length=20)
    improvements: list[str] = Field(default_factory=list, max_length=20)
    revised_example: str = Field(min_length=1, max_length=25000)
    revision_comparison: WritingRevisionComparison | None = None

    @model_serializer
    def _serialize(self) -> dict[str, object]:
        data: dict[str, object] = {
            "rubric_version": self.rubric_version,
            "scores": self.scores.model_dump(),
            "corrections": [c.model_dump() for c in self.corrections],
            "strengths": list(self.strengths),
            "improvements": list(self.improvements),
            "revised_example": self.revised_example,
        }
        if self.revision_comparison is not None:
            data["revision_comparison"] = self.revision_comparison.model_dump()
        return data


class WritingJobState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PENDING", "RETRYABLE", "RUNNING", "SUCCEEDED", "FAILED"]
    stage: str = Field(min_length=1, max_length=64)
    retry_after_seconds: int | None = Field(default=None, ge=1, le=300)
    error_message: str | None = Field(default=None, max_length=500)

    @model_serializer
    def _serialize(self) -> dict[str, object]:
        data: dict[str, object] = {"status": self.status, "stage": self.stage}
        if self.retry_after_seconds is not None:
            data["retry_after_seconds"] = self.retry_after_seconds
        if self.error_message is not None:
            data["error_message"] = self.error_message
        return data


class WritingSubmissionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    revision_group_id: UUID | None = None
    revision_number: int = Field(ge=1, le=4)
    status: Literal["DRAFT", "SUBMITTED", "ACCEPTED", "REJECTED"]
    evaluation_status: WritingEvaluationStatus
    content_item_id: UUID
    edit_version: int = Field(default=0, ge=0)
    submitted_text: str
    word_count: int = Field(ge=0)
    feedback: WritingFeedbackReport | None = None
    job: WritingJobState | None = None


class CreateWritingRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_submission_id: UUID | None = None


class WritingRevisionVersionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    version: int = Field(ge=1, le=4)
    status: Literal["DRAFT", "SUBMITTED", "ACCEPTED", "REJECTED"]
    evaluation_status: WritingEvaluationStatus
    overall_score: int | None = Field(default=None, ge=0, le=100)


class WritingRevisionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_group_id: UUID
    max_revisions: Literal[3] = 3
    versions: list[WritingRevisionVersionSummary] = Field(
        min_length=1, max_length=4
    )
    latest_comparison: WritingRevisionComparison | None = None


WritingPortfolioSort = Literal["recent"]


class WritingPortfolioItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_group_id: UUID
    title: str = Field(min_length=1, max_length=200)
    content_item_id: UUID
    original_submitted_at: datetime
    latest_version: int = Field(ge=1, le=4)
    latest_evaluation_status: WritingEvaluationStatus
    latest_score: int | None = Field(default=None, ge=0, le=100)


class WritingPortfolioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WritingPortfolioItem] = Field(default_factory=list)
    next_cursor: str | None = None








