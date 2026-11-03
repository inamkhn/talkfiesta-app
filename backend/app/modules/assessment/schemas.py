"""Assessment creation and resume API contracts."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from app.modules.onboarding.schemas import AssessmentStatus


class StartAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["INITIAL"]


class StartAssessmentResponse(BaseModel):
    id: UUID
    status: AssessmentStatus
    content_release: str
    estimated_minutes: int = 7
    resumed: bool


class AssessmentDetailResponse(BaseModel):
    id: UUID
    kind: Literal["INITIAL", "REASSESSMENT"]
    status: AssessmentStatus
    content_release: str
    total_items: int
    answered_items: int
    current_position: int | None = None
    can_submit: bool


class PublicChoice(BaseModel):
    id: str
    text: str


class AssessmentItemResponse(BaseModel):
    response_id: UUID
    position: int
    skill: Literal["GRAMMAR", "VOCABULARY", "WRITING", "SPEAKING"]
    kind: Literal["MULTIPLE_CHOICE", "SHORT_WRITING", "RECORDED_SPEAKING"]
    prompt: str
    choices: list[PublicChoice] | None = None
    revision: int
    optional: bool = False


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)


class ChoiceAnswer(AnswerRequest):
    kind: Literal["MULTIPLE_CHOICE"]
    selected_choice_id: str = Field(min_length=1, max_length=128)


class WritingAnswer(AnswerRequest):
    kind: Literal["SHORT_WRITING"]
    text: str = Field(max_length=10000)
    finalize: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def require_final_text(self):
        if self.finalize and not self.text.strip():
            raise ValueError("Final writing submissions must contain text.")
        return self


class SpeakingAnswer(AnswerRequest):
    kind: Literal["RECORDED_SPEAKING"]
    media_upload_id: UUID | None = None
    skipped: bool = Field(default=False, strict=True)
    skip_reason: Literal["MIC_UNAVAILABLE", "DECLINED", "TECHNICAL_ISSUE"] | None = None

    @model_validator(mode="after")
    def require_audio_or_skip(self):
        if self.skipped:
            if self.media_upload_id is not None or self.skip_reason is None:
                raise ValueError("A skip requires a reason and no audio upload.")
        elif self.media_upload_id is None or self.skip_reason is not None:
            raise ValueError("A speaking answer requires audio and no skip reason.")
        return self


SaveAnswerRequest = Annotated[
    ChoiceAnswer | WritingAnswer | SpeakingAnswer, Field(discriminator="kind")
]


class SaveAnswerResponse(BaseModel):
    response_id: UUID
    status: Literal["ASSIGNED", "ANSWERED", "SKIPPED"]
    revision: int
    saved: Literal[True] = True


class SubmitAssessmentResponse(BaseModel):
    attempt_id: UUID
    status: AssessmentStatus
    job_id: UUID
    result_url: str


Cefr = Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class SkillPlacement(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    level: Cefr | None
    assessed: bool
    reason: (
        Literal[
            "MIC_UNAVAILABLE",
            "DECLINED",
            "TECHNICAL_ISSUE",
            "INSUFFICIENT_EVIDENCE",
            "AUDIO_UNAVAILABLE",
            "NOT_ASSESSED",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.assessed and (self.level is None or self.reason is not None):
            raise ValueError(
                "Assessed skills require a level and no missing-evidence reason."
            )
        if not self.assessed and (self.level is not None or self.reason is None):
            raise ValueError("Unassessed skills require a reason and no level.")
        return self


class UnassessedPronunciation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    level: None = None
    assessed: Literal[False] = False
    reason: Literal["AUDIO_PRONUNCIATION_NOT_EVALUATED"] = (
        "AUDIO_PRONUNCIATION_NOT_EVALUATED"
    )


class PlacementSkills(BaseModel):
    grammar: SkillPlacement
    vocabulary: SkillPlacement
    writing: SkillPlacement
    speaking: SkillPlacement
    pronunciation: UnassessedPronunciation = Field(
        default_factory=UnassessedPronunciation
    )


class PublicPlacement(BaseModel):
    cefr: Cefr | None
    provisional: Literal[True] = True
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    skills: PlacementSkills
    strengths: list[str] = Field(max_length=20)
    improvement_priorities: list[str] = Field(max_length=20)
    rubric_version: str = Field(min_length=1, max_length=40)
    assessment_version: str | None = Field(default=None, min_length=1, max_length=60)
    _langsmith_run_id: str | None = PrivateAttr(default=None)


class EvaluationFailure(BaseModel):
    code: Literal["EVALUATION_RETRYABLE", "EVALUATION_FAILED"]
    message: str
    retryable: bool


class EvaluationProgress(BaseModel):
    job_id: UUID | None = None
    status: Literal[
        "NOT_STARTED",
        "QUEUED",
        "RUNNING",
        "RETRY_SCHEDULED",
        "SUCCEEDED",
        "FAILED_FINAL",
    ]
    stage: (
        Literal[
            "WAITING_FOR_WORKER",
            "TRANSCRIBING_AUDIO",
            "EVALUATING_LANGUAGE",
            "DETERMINING_PLACEMENT",
            "SAVING_RESULTS",
            "DONE",
        ]
        | None
    ) = None
    error: EvaluationFailure | None = None


class AssessmentResultResponse(BaseModel):
    assessment_id: UUID
    status: AssessmentStatus
    evaluation: EvaluationProgress
    placement: PublicPlacement | None = None
    retry_after_seconds: int | None = None
    error: EvaluationFailure | None = None
