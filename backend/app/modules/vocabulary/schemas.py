"""Pydantic contracts for the Vocabulary module."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from app.modules.learning.schemas import Cefr

WordMasteryStatus = Literal[
    "NEW", "SUGGESTED", "LEARNING", "REVIEWING", "MASTERED", "DISMISSED"
]
VocabEvaluationStatus = Literal[
    "NOT_REQUIRED", "PENDING", "PROCESSING", "COMPLETED", "FAILED"
]


class VocabularyWordCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    word: str = Field(min_length=1, max_length=120)
    part_of_speech: str = Field(min_length=1, max_length=40)
    definition: str = Field(min_length=1, max_length=1000)
    ipa: str | None = Field(default=None, max_length=120)
    examples: list[str] = Field(min_length=1, max_length=5)
    synonyms: list[str] = Field(default_factory=list, max_length=10)
    antonyms: list[str] = Field(default_factory=list, max_length=10)
    pronunciation_audio_url: str | None = Field(default=None, max_length=500)
    mastery_status: WordMasteryStatus = "NEW"


class VocabularyWordDetailResponse(VocabularyWordCard):
    cefr_level: Cefr | None = None
    mastery_level: int | None = Field(default=None, ge=1, le=5)
    times_practiced: int = Field(default=0, ge=0)
    next_review_at: datetime | None = None
    last_reviewed_at: datetime | None = None


class VocabularyLesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str = Field(min_length=1, max_length=200)
    target_cefr: Cefr
    target_word_count: Literal[10] = 10
    words: list[VocabularyWordCard] = Field(min_length=10, max_length=10)


class VocabularyTodayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: Literal["VOCABULARY"] = "VOCABULARY"
    plan_id: UUID
    module_progress_id: UUID
    cycle: int = Field(ge=1)
    day: int = Field(ge=1, le=21)
    module_status: Literal["ACTIVE", "COMPLETED"]
    lesson: VocabularyLesson | None = None
    existing_practice_session_id: UUID | None = None
    due_review_count: int = Field(ge=0)


class CreateVocabPracticeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_content_id: UUID


class MatchChoiceOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)


class FillBlankQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=64)
    type: Literal["FILL_BLANK"] = "FILL_BLANK"
    prompt: str = Field(min_length=1, max_length=1000)
    choices: list[str] = Field(min_length=2, max_length=6)


class MatchDefinitionQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=64)
    type: Literal["MATCH_DEFINITION"] = "MATCH_DEFINITION"
    prompt: str = Field(min_length=1, max_length=1000)
    choices: list[MatchChoiceOption] = Field(min_length=2, max_length=6)


class UseInContextQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=64)
    type: Literal["USE_IN_CONTEXT"] = "USE_IN_CONTEXT"
    word_id: UUID
    prompt: str = Field(min_length=1, max_length=1000)


VocabQuizQuestion = Annotated[
    FillBlankQuestion | MatchDefinitionQuestion | UseInContextQuestion,
    Field(discriminator="type"),
]


class ObjectiveQuizResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correct: int = Field(ge=0)
    total: int = Field(ge=0)


class ContextUsageFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=64)
    word_id: UUID
    meaning_used_correctly: bool | None = None
    grammar_acceptable: bool | None = None
    explanation: str = Field(min_length=1, max_length=500)
    suggested_revision: str | None = Field(default=None, max_length=500)


class VocabPracticeSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: Literal["DRAFT", "SUBMITTED", "ACCEPTED", "REJECTED"]
    mode: Literal["VOCAB_QUIZ"] = "VOCAB_QUIZ"
    edit_version: int = Field(ge=0)
    questions: list[VocabQuizQuestion] = Field(min_length=1, max_length=30)
    saved_answers: dict[str, str] = Field(default_factory=dict)
    evaluation_status: VocabEvaluationStatus | None = None
    objective_result: ObjectiveQuizResult | None = None
    context_result: list[ContextUsageFeedback] | None = None


class VocabAnswerItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=64)
    choice_id: str | None = Field(default=None, min_length=1, max_length=120)
    text: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_choice_or_text(self):
        if (self.choice_id is None) == (self.text is None):
            raise ValueError("Provide either choice_id or text for each answer.")
        return self


class SaveVocabPracticeAnswersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_edit_version: int = Field(ge=0, strict=True)
    answers: list[VocabAnswerItem] = Field(min_length=1, max_length=30)


class SaveVocabPracticeAnswersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: Literal["DRAFT"] = "DRAFT"
    edit_version: int = Field(ge=0)
    saved_answer_count: int = Field(ge=0)


class SubmitVocabPracticeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[VocabAnswerItem] | None = Field(default=None, max_length=30)


class SubmitVocabPracticeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    activity_status: Literal["COMPLETED"] = "COMPLETED"
    evaluation_status: VocabEvaluationStatus
    objective_result: ObjectiveQuizResult
    context_result: list[ContextUsageFeedback] | None = None
    job_id: UUID | None = None
    next_module_day: int | None = Field(default=None, ge=1, le=21)


class DueReviewExercise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["RECALL"] = "RECALL"
    prompt: str = Field(min_length=1, max_length=500)
    choices: list[MatchChoiceOption] | None = Field(default=None, min_length=2, max_length=6)

    @model_serializer
    def _serialize(self) -> dict[str, object]:
        data: dict[str, object] = {"type": self.type, "prompt": self.prompt}
        if self.choices is not None:
            data["choices"] = [c.model_dump() for c in self.choices]
        return data


class DueReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_vocabulary_id: UUID
    word: str = Field(min_length=1, max_length=120)
    mastery_level: int = Field(ge=1, le=5)
    status: Literal["LEARNING", "REVIEWING"]
    next_review_at: datetime
    is_overdue: bool
    exercise: DueReviewExercise


class DueReviewsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    items: list[DueReviewItem] = Field(default_factory=list)
    next_cursor: str | None = None


class SubmitVocabReviewAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["RECALL"] = "RECALL"
    selected_choice_id: str | None = Field(default=None, min_length=1, max_length=120)
    text: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_choice_or_text(self):
        if (self.selected_choice_id is None) == (self.text is None):
            raise ValueError("Provide either selected_choice_id or text for the review answer.")
        return self


class SubmitVocabReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_vocabulary_id: UUID
    answer: SubmitVocabReviewAnswer


class SubmitVocabReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_vocabulary_id: UUID
    correct: bool
    previous_mastery_level: int = Field(ge=1, le=5)
    mastery_level: int = Field(ge=1, le=5)
    status: Literal["LEARNING", "REVIEWING", "MASTERED"]
    next_review_at: datetime | None = None
    times_reviewed: int = Field(ge=1)


VocabularyBankStatus = Literal["LEARNING", "REVIEWING", "MASTERED"]


class VocabularyBankItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word_key: str = Field(min_length=1, max_length=120)
    word_content_id: UUID | None = None
    status: VocabularyBankStatus
    mastery_level: int = Field(ge=1, le=5)
    times_practiced: int = Field(ge=0)
    next_review_at: datetime | None = None


class VocabularyBankResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[VocabularyBankItem] = Field(default_factory=list)
    next_cursor: str | None = None


class VocabularyProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learned_distinct: int = Field(ge=0)
    mastered: int = Field(ge=0)
    learning: int = Field(ge=0)
    reviewing: int = Field(ge=0)
    due_reviews: int = Field(ge=0)
    overdue_reviews: int = Field(ge=0)
    current_module_day: int = Field(ge=1, le=21)
    completed_curriculum_days: int = Field(ge=0, le=21)



