"""Versioned deterministic CEFR placement policy (placement-v1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.modules.assessment.blueprint import LEVELS
from app.modules.assessment.schemas import (
    Cefr,
    PlacementSkills,
    PublicPlacement,
    SkillPlacement,
)


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
    if not outcomes:
        raise ValueError(f"Missing objective outcomes for {skill}")

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
        final_idx = round((current_idx + highest_correct_idx) / 2)
        final_idx = max(0, min(len(LEVELS) - 1, final_idx))

    level: Cefr = LEVELS[final_idx]
    correct_count = sum(1 for item in outcomes if item.correct)
    label = skill.lower()
    strengths: list[str] = []
    priorities: list[str] = []
    if correct_count >= 3:
        strengths.append(f"Solid {label} accuracy at {level} level")
    else:
        priorities.append(f"Strengthen core {label} patterns around {level}")

    return SkillPlacement(level=level, assessed=True), strengths, priorities


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
    if not writing.assessed or writing.level is None:
        raise ValueError("Required writing evidence must be assessed.")

    grammar_skill, g_strengths, g_priorities = grade_objective_skill(
        "GRAMMAR", grammar_outcomes
    )
    vocab_skill, v_strengths, v_priorities = grade_objective_skill(
        "VOCABULARY", vocabulary_outcomes
    )
    writing_skill = SkillPlacement(level=writing.level, assessed=True)
    speaking_skill = (
        SkillPlacement(level=speaking.level, assessed=True)
        if speaking.assessed and speaking.level is not None
        else SkillPlacement(
            level=None,
            assessed=False,
            reason=speaking.reason or "NOT_ASSESSED",
        )
    )

    g_idx = LEVELS.index(grammar_skill.level)
    v_idx = LEVELS.index(vocab_skill.level)
    w_idx = LEVELS.index(writing_skill.level)

    if speaking_skill.assessed and speaking_skill.level is not None:
        s_idx = LEVELS.index(speaking_skill.level)
        # Productive skills (writing + speaking) carry 60%, objective 40%
        weighted = 0.20 * g_idx + 0.20 * v_idx + 0.30 * w_idx + 0.30 * s_idx
        spread = max(g_idx, v_idx, w_idx, s_idx) - min(g_idx, v_idx, w_idx, s_idx)
        confidence: Literal["LOW", "MEDIUM", "HIGH"] = (
            "HIGH" if spread <= 2 else "MEDIUM"
        )
    else:
        # Speaking unassessed: writing carries 40%, grammar 30%, vocabulary 30%
        weighted = 0.30 * g_idx + 0.30 * v_idx + 0.40 * w_idx
        spread = max(g_idx, v_idx, w_idx) - min(g_idx, v_idx, w_idx)
        confidence = "MEDIUM" if spread <= 2 else "LOW"

    overall_idx = max(0, min(len(LEVELS) - 1, round(weighted)))
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

