"""Conservative provisional placement heuristic; not a calibrated CEFR measure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.modules.assessment.blueprint import LEVELS, SEQUENCE
from app.modules.assessment.schemas import (
    Cefr,
    PlacementSkills,
    PublicPlacement,
    SkillPlacement,
)

PLACEMENT_POLICY_VERSION = "placement-policy-v2"


def _nearest_band(numerator: int, denominator: int) -> int:
    """Exact integer rounding to nearest band; halfway ties choose the lower band."""
    band, remainder = divmod(numerator, denominator)
    return band + int(2 * remainder > denominator)


@dataclass(frozen=True)
class ObjectiveItemOutcome:
    cefr_level: Cefr
    correct: bool


@dataclass(frozen=True)
class EvaluatedSkillFeedback:
    assessed: bool
    level: Cefr | None = None
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
    strengths: tuple[str, ...] = ()
    improvement_priorities: tuple[str, ...] = ()


def grade_objective_skill(
    skill: Literal["GRAMMAR", "VOCABULARY"],
    outcomes: list[ObjectiveItemOutcome],
) -> tuple[SkillPlacement, list[str], list[str]]:
    """Estimate objective skill CEFR from adaptive question levels and correctness."""
    if skill not in ("GRAMMAR", "VOCABULARY"):
        raise ValueError("Unknown objective skill.")
    if len(outcomes) != SEQUENCE.count(skill):
        raise ValueError("Objective evidence must match the assessment blueprint.")
    if any(
        item.cefr_level not in LEVELS or type(item.correct) is not bool
        for item in outcomes
    ):
        raise ValueError(
            "Objective evidence requires valid CEFR bands and boolean grades."
        )

    # Track the adaptive path: start from the first item's band and step +1/-1
    current_idx = LEVELS.index(outcomes[0].cefr_level)
    highest_correct_idx: int | None = None
    for item in outcomes:
        item_idx = LEVELS.index(item.cefr_level)
        if item.correct:
            if highest_correct_idx is None or item_idx > highest_correct_idx:
                highest_correct_idx = item_idx
            current_idx = min(len(LEVELS) - 1, item_idx + 1)
        else:
            current_idx = max(0, item_idx - 1)

    if highest_correct_idx is None:
        final_idx = 0
    else:
        final_idx = min(
            highest_correct_idx,
            _nearest_band(current_idx + highest_correct_idx, 2),
        )

    level: Cefr = LEVELS[final_idx]
    correct_count = sum(1 for item in outcomes if item.correct)
    label = skill.lower()
    strengths: list[str] = []
    priorities: list[str] = []
    if correct_count >= 3:
        strengths.append(
            f"Answered {correct_count} of {len(outcomes)} {label} questions correctly"
        )
    else:
        priorities.append(f"Strengthen core {label} patterns around {level}")

    return SkillPlacement(level=level, assessed=True), strengths, priorities


def _productive_skill(feedback: EvaluatedSkillFeedback) -> SkillPlacement:
    """Reject contradictory evidence instead of silently repairing it."""
    placement = SkillPlacement(
        level=feedback.level,
        assessed=feedback.assessed,
        reason=feedback.reason,
    )
    if not placement.assessed and (
        feedback.strengths or feedback.improvement_priorities
    ):
        raise ValueError("Unassessed skills cannot contribute scored feedback.")
    for text in (*feedback.strengths, *feedback.improvement_priorities):
        if not isinstance(text, str) or not text.strip() or len(text.strip()) > 600:
            raise ValueError("Skill feedback must be nonblank and bounded.")
    return placement


def _dedupe_bounded(items: list[str], *, fallback: str, limit: int = 5) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in items:
        text = raw.strip()
        if not text:
            continue
        key = text.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned or [fallback]


def assign_provisional_cefr(
    *,
    grammar_outcomes: list[ObjectiveItemOutcome],
    vocabulary_outcomes: list[ObjectiveItemOutcome],
    writing: EvaluatedSkillFeedback,
    speaking: EvaluatedSkillFeedback,
    rubric_version: str | None = None,
) -> PublicPlacement:
    """Combine objective and AI-evaluated skills into a validated PublicPlacement."""
    writing_skill = _productive_skill(writing)
    speaking_skill = _productive_skill(speaking)
    if not writing_skill.assessed:
        raise ValueError("Required writing evidence must be assessed.")

    grammar_skill, g_strengths, g_priorities = grade_objective_skill(
        "GRAMMAR", grammar_outcomes
    )
    vocab_skill, v_strengths, v_priorities = grade_objective_skill(
        "VOCABULARY", vocabulary_outcomes
    )
    g_idx = LEVELS.index(grammar_skill.level)
    v_idx = LEVELS.index(vocab_skill.level)
    w_idx = LEVELS.index(writing_skill.level)

    if speaking_skill.assessed and speaking_skill.level is not None:
        s_idx = LEVELS.index(speaking_skill.level)
        # Productive skills (writing + speaking) carry 60%, objective 40%
        weighted_tenths = 2 * g_idx + 2 * v_idx + 3 * w_idx + 3 * s_idx
        spread = max(g_idx, v_idx, w_idx, s_idx) - min(g_idx, v_idx, w_idx, s_idx)
        # Agreement is not statistical calibration. Never report HIGH for this
        # short blueprint; broad disagreement or absent objective success is LOW.
        confidence: Literal["LOW", "MEDIUM"] = (
            "MEDIUM"
            if spread <= 1
            and any(item.correct for item in grammar_outcomes)
            and any(item.correct for item in vocabulary_outcomes)
            else "LOW"
        )
    else:
        # Speaking unassessed: writing carries 40%, grammar 30%, vocabulary 30%
        weighted_tenths = 3 * g_idx + 3 * v_idx + 4 * w_idx
        confidence = "LOW"

    overall_idx = _nearest_band(weighted_tenths, 10)
    overall_cefr: Cefr = LEVELS[overall_idx]

    strengths = _dedupe_bounded(
        [
            *writing.strengths,
            *speaking.strengths,
            *g_strengths,
            *v_strengths,
        ],
        fallback=f"Demonstrates foundational {overall_cefr} communication ability",
    )
    improvement_priorities = _dedupe_bounded(
        [
            *writing.improvement_priorities,
            *speaking.improvement_priorities,
            *g_priorities,
            *v_priorities,
        ],
        fallback=f"Build consistency across {overall_cefr} productive tasks",
    )

    return PublicPlacement(
        cefr=overall_cefr,
        provisional=True,
        confidence=confidence,
        skills=PlacementSkills(
            grammar=grammar_skill,
            vocabulary=vocab_skill,
            writing=writing_skill,
            speaking=speaking_skill,
        ),
        strengths=strengths,
        improvement_priorities=improvement_priorities,
        rubric_version=rubric_version or settings.assessment_rubric_version,
    )
