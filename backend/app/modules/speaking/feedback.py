"""Shared Speaking feedback contracts without provider dependencies."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

RUBRIC_VERSION = "speaking-feedback-v1"
Text = Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )


class Scores(StrictModel):
    grammar: int = Field(ge=0, le=100)
    vocabulary: int = Field(ge=0, le=100)
    coherence: int = Field(ge=0, le=100)
    task_relevance: int = Field(ge=0, le=100)


class Correction(StrictModel):
    original: Text
    corrected: Text
    explanation: Text


class LanguageFeedback(StrictModel):
    reviewable: bool
    reason: Literal["NO_USABLE_SPEECH"] | None
    scores: Scores | None
    corrections: list[Correction] = Field(max_length=8)
    strengths: list[Text] = Field(max_length=4)
    next_steps: list[Text] = Field(max_length=4)
    improved_answer: str | None = Field(max_length=6000)

    @model_validator(mode="after")
    def consistent(self):
        if self.reviewable:
            if (
                self.reason is not None
                or self.scores is None
                or not self.strengths
                or not self.next_steps
                or not self.improved_answer
            ):
                raise ValueError("Reviewable speech requires grounded coaching")
        elif (
            self.reason != "NO_USABLE_SPEECH"
            or self.scores is not None
            or self.corrections
            or self.strengths
            or self.next_steps
            or self.improved_answer is not None
        ):
            raise ValueError("Unscorable speech cannot have invented feedback")
        return self


class AudioMetrics(StrictModel):
    recording_duration_seconds: float = Field(gt=0)
    approx_recording_wpm: float | None = Field(ge=0)
    pause_count: None = None


class SpeakingFeedback(LanguageFeedback):
    audio_metrics: AudioMetrics
    pronunciation_score: None = None
    retry_suggestion: str | None = None
