"""Internal evaluation contracts; provider output is never a placement decision."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    StringConstraints,
    model_validator,
)

from app.modules.assessment.schemas import (
    Cefr,
    PlacementSkills,
    PublicPlacement,
    SkillPlacement,
)

FeedbackText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)
]
FeedbackList = Annotated[list[FeedbackText], Field(max_length=4)]


class StrictOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )


class CriterionEvaluation(StrictOutput):
    """A qualitative CEFR judgment, not an uncalibrated numeric score."""

    level: Cefr
    feedback: FeedbackText = Field(repr=False)


class LanguageCriteria(StrictOutput):
    grammar: CriterionEvaluation
    vocabulary: CriterionEvaluation
    coherence: CriterionEvaluation
    task_completion: CriterionEvaluation


class LanguageEvaluation(StrictOutput):
    # Nullable fields are required, so insufficient evidence must be explicit.
    sufficient_evidence: bool
    cefr_level: Cefr | None
    reason: Literal["INSUFFICIENT_EVIDENCE"] | None
    criteria: LanguageCriteria | None = Field(repr=False)
    strengths: FeedbackList = Field(repr=False)
    improvement_priorities: FeedbackList = Field(repr=False)

    @model_validator(mode="after")
    def consistent_evidence(self):
        if self.sufficient_evidence:
            if (
                self.cefr_level is None
                or self.criteria is None
                or self.reason is not None
            ):
                raise ValueError(
                    "Assessed language requires a level and criteria, without a reason."
                )
            if not self.strengths or not self.improvement_priorities:
                raise ValueError(
                    "Assessed language requires strengths and improvement priorities."
                )
        elif (
            self.cefr_level is not None
            or self.criteria is not None
            or self.reason != "INSUFFICIENT_EVIDENCE"
            or self.strengths
            or self.improvement_priorities
        ):
            raise ValueError(
                "Insufficient evidence requires null scores, an explicit reason, and empty feedback."
            )
        return self


class WritingEvaluation(LanguageEvaluation):
    """Writing quality against the supplied task and versioned rubric."""


class SpeakingLanguageEvaluation(LanguageEvaluation):
    """Transcript language only; pronunciation, pace, and prosody are not inferred."""


class ValidatedSkillPlacement(SkillPlacement):
    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )


class ValidatedPlacementSkills(PlacementSkills):
    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )
    grammar: ValidatedSkillPlacement
    vocabulary: ValidatedSkillPlacement
    writing: ValidatedSkillPlacement
    speaking: ValidatedSkillPlacement


class PlacementResult(PublicPlacement):
    """Strict persistence boundary for the server's deterministic placement policy."""

    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )
    cefr: Cefr
    confidence: Literal["LOW", "MEDIUM"]
    skills: ValidatedPlacementSkills
    strengths: Annotated[list[FeedbackText], Field(min_length=1, max_length=20)]
    improvement_priorities: Annotated[
        list[FeedbackText], Field(min_length=1, max_length=20)
    ]

    @model_validator(mode="after")
    def required_skills(self):
        if not all(
            (
                self.skills.grammar.assessed,
                self.skills.vocabulary.assessed,
                self.skills.writing.assessed,
            )
        ):
            raise ValueError(
                "Completed placement requires grammar, vocabulary, and writing evidence."
            )
        if not self.skills.speaking.assessed and self.confidence != "LOW":
            raise ValueError(
                "This placement policy requires low confidence without speaking evidence."
            )
        if not self.rubric_version.strip():
            raise ValueError("Placement requires a nonblank rubric version.")
        return self


class ResponseEvaluation(StrictOutput):
    """Server-bound evaluation; the model never chooses response IDs or revisions."""

    response_id: UUID
    question_id: UUID
    revision: int = Field(ge=1)
    skill: Literal["WRITING", "SPEAKING"]
    placement: ValidatedSkillPlacement
    language: LanguageEvaluation | None = Field(repr=False)

    @model_validator(mode="after")
    def match_language(self):
        if self.language is None:
            if self.placement.assessed or self.skill == "WRITING":
                raise ValueError("Assessed responses require language evaluation.")
        elif (
            self.language.sufficient_evidence != self.placement.assessed
            or self.language.cefr_level != self.placement.level
            or self.language.reason != self.placement.reason
        ):
            raise ValueError("Language evaluation and skill placement disagree.")
        return self


class AssessmentEvaluation(StrictOutput):
    placement: PlacementResult
    responses: list[ResponseEvaluation] = Field(min_length=2, max_length=2, repr=False)
    _langsmith_run_id: str | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def match_responses(self):
        if {r.skill for r in self.responses} != {"WRITING", "SPEAKING"} or len(
            {r.response_id for r in self.responses}
        ) != 2:
            raise ValueError("One distinct response per productive skill is required.")
        for response in self.responses:
            if response.placement != getattr(
                self.placement.skills, response.skill.lower()
            ):
                raise ValueError("Response evaluation and final placement disagree.")
        return self
