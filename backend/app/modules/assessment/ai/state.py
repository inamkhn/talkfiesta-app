"""Typed state and structured-output schemas for the assessment LangGraph pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID

from app.modules.assessment.ai.checkpoints import CheckpointStore
from app.modules.assessment.ai.schemas import LanguageEvaluation
from app.modules.assessment.placement_policy import (
    EvaluatedSkillFeedback,
    ObjectiveItemOutcome,
)
from app.modules.assessment.schemas import PublicPlacement


@dataclass(frozen=True)
class FrozenSpeakingEvidence:
    skipped: bool
    skip_reason: Literal["MIC_UNAVAILABLE", "DECLINED", "TECHNICAL_ISSUE"] | None = None
    prompt: str = ""
    rubric: dict | None = None
    object_key: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    checksum_sha256: str | None = None
    delete_after: datetime | None = None


@dataclass(frozen=True)
class FrozenWritingEvidence:
    prompt: str
    rubric: dict
    text: str


@dataclass(frozen=True)
class FrozenAssessment:
    job_id: UUID
    attempt_id: UUID
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
    writing_evaluation: LanguageEvaluation
    speaking_evaluation: LanguageEvaluation | None
    checkpoints: CheckpointStore
