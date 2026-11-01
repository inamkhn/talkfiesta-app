"""Typed state and structured-output schemas for the assessment LangGraph pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assessment.placement_policy import (
    EvaluatedSkillFeedback,
    ObjectiveItemOutcome,
)
from app.modules.assessment.schemas import Cefr, PublicPlacement


class StructuredLanguageEvaluation(BaseModel):
    """Strict structured output returned by the LLM for writing or speaking."""

    model_config = ConfigDict(extra="forbid")

    cefr_level: Cefr
    sufficient_evidence: bool
    strengths: list[str] = Field(min_length=1, max_length=4)
    improvement_priorities: list[str] = Field(min_length=1, max_length=4)


@dataclass(frozen=True)
class FrozenSpeakingEvidence:
    skipped: bool
    skip_reason: (
        Literal["MIC_UNAVAILABLE", "DECLINED", "TECHNICAL_ISSUE"] | None
    ) = None
    prompt: str = ""
    rubric: dict | None = None
    object_key: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    checksum_sha256: str | None = None


@dataclass(frozen=True)
class FrozenWritingEvidence:
    prompt: str
    rubric: dict
    text: str


@dataclass(frozen=True)
class FrozenAssessment:
    job_id: UUID
    attempt_id: UUID
    user_id: UUID
    grammar_outcomes: list[ObjectiveItemOutcome]
    vocabulary_outcomes: list[ObjectiveItemOutcome]
    writing: FrozenWritingEvidence
    speaking: FrozenSpeakingEvidence


class AssessmentGraphState(TypedDict, total=False):
    evidence: FrozenAssessment
    report_stage: Callable[[str], None] | None
    writing_feedback: EvaluatedSkillFeedback
    speaking_feedback: EvaluatedSkillFeedback
    placement: PublicPlacement

