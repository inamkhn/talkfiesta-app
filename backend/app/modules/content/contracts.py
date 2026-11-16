"""Typed Pydantic content contracts and learner redaction helpers (Content Factory V1)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
GoalVariant = Literal["GENERAL", "BUSINESS", "TRAVEL"]
ContentModule = Literal["VOCABULARY", "SPEAKING", "WRITING"]
SpeakingExerciseType = Literal["CONVERSATIONAL", "IMPROMPTU", "PUBLIC_SPEAKING"]
WritingType = Literal["DESCRIPTIVE", "NARRATIVE", "OPINION", "ARGUMENTATIVE"]

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ItemKeyStr = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]


class StrictContentModel(BaseModel):
    """Base contract rejecting unexpected fields from model or editor inputs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PrivateEvaluationSection(StrictContentModel):
    """Internal-only rubric/answer guidance; never serialized to learner APIs."""

    rubric_version: NonEmptyStr = Field(max_length=60)
    criteria: list[NonEmptyStr] = Field(min_length=1, max_length=6)
    sample_response: str | None = Field(default=None, max_length=2500)
    explanations: dict[str, str] = Field(default_factory=dict)


class VocabReviewChoice(StrictContentModel):
    id: Literal["a", "b", "c", "d"]
    text: NonEmptyStr = Field(max_length=300)


class VocabReviewExercise(StrictContentModel):
    prompt: NonEmptyStr = Field(max_length=400)
    choices: list[VocabReviewChoice] = Field(min_length=3, max_length=4)
    correct_choice_id: Literal["a", "b", "c", "d"] = "a"

    @model_validator(mode="after")
    def validate_correct_choice_exists(self):
        ids = {c.id for c in self.choices}
        if len(ids) != len(self.choices):
            raise ValueError("Review exercise choices must have distinct IDs.")
        if self.correct_choice_id not in ids:
            raise ValueError("correct_choice_id must match one of the choices.")
        return self


class VocabWordContract(StrictContentModel):
    """Schema for a `VOCAB_WORD` content item body."""

    item_key: ItemKeyStr
    word: NonEmptyStr = Field(max_length=80)
    lemma: NonEmptyStr = Field(max_length=80)
    part_of_speech: Literal[
        "noun",
        "verb",
        "adjective",
        "adverb",
        "phrase",
        "preposition",
        "conjunction",
    ]
    cefr_level: CefrLevel
    definition: NonEmptyStr = Field(max_length=400)
    ipa: str | None = Field(default=None, max_length=120)
    pronunciation_hint: str | None = Field(default=None, max_length=120)
    examples: list[NonEmptyStr] = Field(min_length=1, max_length=4)
    collocations: list[NonEmptyStr] = Field(default_factory=list, max_length=6)
    synonyms: list[NonEmptyStr] = Field(default_factory=list, max_length=5)
    antonyms: list[NonEmptyStr] = Field(default_factory=list, max_length=5)
    common_mistakes: list[NonEmptyStr] = Field(default_factory=list, max_length=4)
    review_exercise: VocabReviewExercise


class FillBlankExerciseContract(StrictContentModel):
    item_id: ItemKeyStr
    type: Literal["FILL_BLANK"] = "FILL_BLANK"
    prompt: NonEmptyStr = Field(max_length=500)
    choices: list[NonEmptyStr] = Field(min_length=3, max_length=4)
    correct_choice: NonEmptyStr = Field(max_length=100)


class MatchChoiceContract(StrictContentModel):
    id: Literal["a", "b", "c", "d"]
    text: NonEmptyStr = Field(max_length=300)


class MatchDefinitionExerciseContract(StrictContentModel):
    item_id: ItemKeyStr
    type: Literal["MATCH_DEFINITION"] = "MATCH_DEFINITION"
    prompt: NonEmptyStr = Field(max_length=500)
    choices: list[MatchChoiceContract] = Field(min_length=3, max_length=4)
    correct_choice_id: Literal["a", "b", "c", "d"]


class UseInContextExerciseContract(StrictContentModel):
    item_id: ItemKeyStr
    type: Literal["USE_IN_CONTEXT"] = "USE_IN_CONTEXT"
    word_item_key: ItemKeyStr | None = None
    word_id: UUID | None = None
    prompt: NonEmptyStr = Field(max_length=500)

    @model_validator(mode="after")
    def require_word_reference(self):
        if self.word_item_key is None and self.word_id is None:
            raise ValueError(
                "USE_IN_CONTEXT exercise requires word_item_key or word_id."
            )
        return self


VocabExerciseContract = Annotated[
    FillBlankExerciseContract
    | MatchDefinitionExerciseContract
    | UseInContextExerciseContract,
    Field(discriminator="type"),
]


class VocabularyLessonContract(StrictContentModel):
    """Schema for a `VOCABULARY_LESSON` content item body."""

    item_key: ItemKeyStr
    theme: NonEmptyStr = Field(max_length=160)
    learning_objective: NonEmptyStr = Field(max_length=300)
    description: NonEmptyStr = Field(max_length=400)
    instructions: NonEmptyStr = Field(max_length=600)
    estimated_minutes: int = Field(default=10, ge=3, le=45)
    word_item_keys: list[ItemKeyStr] = Field(default_factory=list, max_length=10)
    word_content_ids: list[UUID] = Field(default_factory=list, max_length=10)
    exercises: list[VocabExerciseContract] = Field(min_length=3, max_length=12)
    private_evaluation: PrivateEvaluationSection | None = None

    @model_validator(mode="after")
    def require_ten_word_references(self):
        if len(self.word_item_keys) != 10 and len(self.word_content_ids) != 10:
            raise ValueError(
                "Vocabulary lesson requires exactly 10 word_item_keys or 10 word_content_ids."
            )
        return self


class VocabularyUnitOutput(StrictContentModel):
    """Complete generated Vocabulary day unit (1 lesson + 10 distinct words)."""

    lesson: VocabularyLessonContract
    words: list[VocabWordContract] = Field(min_length=10, max_length=10)


class SpeakingLessonContract(StrictContentModel):
    """Schema for a `SPEAKING_LESSON` content item body."""

    item_key: ItemKeyStr
    theme: NonEmptyStr = Field(max_length=160)
    learning_objective: NonEmptyStr = Field(max_length=300)
    description: NonEmptyStr = Field(max_length=400)
    estimated_minutes: int = Field(default=10, ge=3, le=45)
    exercise_type: SpeakingExerciseType
    topic: NonEmptyStr = Field(max_length=200)
    title: NonEmptyStr = Field(max_length=200)
    prompt: NonEmptyStr = Field(max_length=600)
    instructions: NonEmptyStr = Field(max_length=600)
    preparation_questions: list[NonEmptyStr] = Field(min_length=2, max_length=5)
    target_duration_seconds: int = Field(ge=20, le=180)
    preparation_seconds: int = Field(ge=5, le=60)
    target_vocabulary: list[NonEmptyStr] = Field(min_length=2, max_length=10)
    target_grammar: list[NonEmptyStr] = Field(min_length=1, max_length=5)
    tips: list[NonEmptyStr] = Field(min_length=2, max_length=5)
    learner_success_criteria: list[NonEmptyStr] = Field(min_length=2, max_length=5)
    private_evaluation: PrivateEvaluationSection


class WritingLessonContract(StrictContentModel):
    """Schema for a `WRITING_LESSON` content item body."""

    item_key: ItemKeyStr
    theme: NonEmptyStr = Field(max_length=160)
    learning_objective: NonEmptyStr = Field(max_length=300)
    description: NonEmptyStr = Field(max_length=400)
    estimated_minutes: int = Field(default=15, ge=5, le=60)
    writing_type: WritingType
    title: NonEmptyStr = Field(max_length=200)
    prompt: NonEmptyStr = Field(max_length=600)
    instructions: NonEmptyStr = Field(max_length=600)
    target_word_count: int = Field(ge=25, le=400)
    minimum_word_count: int = Field(ge=15, le=300)
    maximum_word_count: int = Field(ge=40, le=600)
    time_limit_minutes: int = Field(ge=5, le=45)
    target_grammar: list[NonEmptyStr] = Field(min_length=1, max_length=5)
    target_vocabulary: list[NonEmptyStr] = Field(min_length=2, max_length=10)
    structure_guidance: list[NonEmptyStr] = Field(min_length=2, max_length=5)
    tips: list[NonEmptyStr] = Field(min_length=2, max_length=5)
    learner_success_criteria: list[NonEmptyStr] = Field(min_length=2, max_length=5)
    private_evaluation: PrivateEvaluationSection

    @model_validator(mode="after")
    def validate_word_bounds(self):
        if not (
            self.minimum_word_count
            < self.target_word_count
            <= self.maximum_word_count
        ):
            raise ValueError(
                "Writing word counts must satisfy minimum_word_count < target_word_count <= maximum_word_count."
            )
        return self


class AiReviewScores(StrictContentModel):
    cefr_fit: int = Field(ge=1, le=5)
    objective_alignment: int = Field(ge=1, le=5)
    language_correctness: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    pedagogical_value: int = Field(ge=1, le=5)
    progression_and_uniqueness: int = Field(ge=1, le=5)
    exercise_validity: int = Field(ge=1, le=5)


class AiReviewReport(StrictContentModel):
    """Structured independent quality review output (never written to learner views)."""

    overall_decision: Literal[
        "PASS_TO_HUMAN_REVIEW", "REGENERATE", "NEEDS_EDITOR_REVIEW"
    ]
    scores: AiReviewScores
    critical_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_action: NonEmptyStr = Field(max_length=300)

    def meets_auto_review_bar(self) -> bool:
        """Spec Section 6.7: no critical issues and all dimensions >= 4."""
        if self.critical_issues:
            return False
        values = (
            self.scores.cefr_fit,
            self.scores.objective_alignment,
            self.scores.language_correctness,
            self.scores.clarity,
            self.scores.pedagogical_value,
            self.scores.progression_and_uniqueness,
            self.scores.exercise_validity,
        )
        return all(score >= 4 for score in values)


_PRIVATE_KEYS = frozenset(
    {
        "private_evaluation",
        "correct_choice",
        "correct_choice_id",
        "answer_key",
        "sample_response",
        "sample_answer",
        "explanations",
    }
)


def redact_for_learner(payload: dict) -> dict:
    """Recursively strip private evaluator and answer-key fields from content JSON."""
    cleaned: dict = {}
    for key, value in payload.items():
        if key in _PRIVATE_KEYS:
            continue
        if isinstance(value, dict):
            cleaned[key] = redact_for_learner(value)
        elif isinstance(value, list):
            cleaned[key] = [
                redact_for_learner(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned

