"""Unit tests for the initial assessment evaluator, LangGraph workflow, and placement policy."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.ai.langchain_models import (
    _local_fallback_evaluation,
    is_usable_learner_evidence,
)
from app.modules.assessment.ai.nodes import _anchor_language_evaluation
from app.modules.assessment.ai.schemas import WritingEvaluation
from app.modules.assessment.placement_policy import (
    EvaluatedSkillFeedback,
    ObjectiveItemOutcome,
    assign_provisional_cefr,
)


def _sample_objective(
    levels_and_correct: list[tuple[str, bool]],
) -> list[ObjectiveItemOutcome]:
    return [
        ObjectiveItemOutcome(cefr_level=level, correct=correct)
        for level, correct in levels_and_correct
    ]


def test_assign_provisional_cefr_with_skipped_speaking() -> None:
    placement = assign_provisional_cefr(
        grammar_outcomes=_sample_objective(
            [("A2", True), ("B1", True), ("B2", False), ("B1", True)]
        ),
        vocabulary_outcomes=_sample_objective(
            [("A2", True), ("B1", False), ("A2", True), ("B1", True)]
        ),
        writing=EvaluatedSkillFeedback(
            assessed=True,
            level="B1",
            strengths=("Clear paragraph structure",),
            improvement_priorities=("Use more varied connectors",),
        ),
        speaking=EvaluatedSkillFeedback(
            assessed=False,
            level=None,
            reason="MIC_UNAVAILABLE",
        ),
    )
    assert placement.cefr == "B1"
    assert placement.provisional is True
    assert placement.confidence == "LOW"
    assert placement.skills.grammar.assessed is True
    assert placement.skills.vocabulary.assessed is True
    assert placement.skills.writing.level == "B1"
    assert placement.skills.speaking.assessed is False
    assert placement.skills.speaking.reason == "MIC_UNAVAILABLE"


def test_assign_provisional_cefr_rejects_unassessed_writing() -> None:
    with pytest.raises(ValueError, match="Required writing evidence"):
        assign_provisional_cefr(
            grammar_outcomes=_sample_objective([("A2", True)] * 4),
            vocabulary_outcomes=_sample_objective([("A2", True)] * 4),
            writing=EvaluatedSkillFeedback(assessed=False, level=None),
            speaking=EvaluatedSkillFeedback(
                assessed=False, level=None, reason="DECLINED"
            ),
        )


def test_usable_learner_evidence_rejects_short_gibberish_and_prompt_copy() -> None:
    prompt = "Describe a recent project you worked on and what skill you want to improve next."
    assert is_usable_learner_evidence("Too short", task_prompt=prompt) is False
    assert (
        is_usable_learner_evidence(
            "asdfghjkl qwertyuiop zxcvbnm bnmvcxz lkjhgfdsa", task_prompt=prompt
        )
        is False
    )
    assert (
        is_usable_learner_evidence(
            "good good good good good good good good", task_prompt=prompt
        )
        is False
    )
    assert is_usable_learner_evidence(prompt, task_prompt=prompt) is False
    assert (
        is_usable_learner_evidence(
            "Recently, I built an automated reporting dashboard using Python and SQL to track weekly team performance.",
            task_prompt=prompt,
        )
        is True
    )


def test_anchor_language_evaluation_clamps_hallucinated_cefr_and_short_text() -> None:
    inflated = WritingEvaluation.model_validate(
        {
            "sufficient_evidence": True,
            "cefr_level": "C2",
            "reason": None,
            "criteria": {
                "grammar": {"level": "A2", "feedback": "Basic clause control."},
                "vocabulary": {"level": "A2", "feedback": "Everyday words."},
                "coherence": {"level": "B1", "feedback": "Simple transitions."},
                "task_completion": {"level": "A2", "feedback": "Brief answer."},
            },
            "strengths": ["Clear basic message"],
            "improvement_priorities": ["Add more detail"],
        }
    )
    anchored = _anchor_language_evaluation(
        WritingEvaluation,
        inflated,
        text="Yesterday I worked on a small project with my team and learned basic git commands for our repository.",
        task_prompt="Write about your recent work.",
    )
    # Criteria average is A2 (idx 1), so C2 is clamped to B1 (idx 2)
    assert anchored.cefr_level == "B1"


def test_local_fallback_evaluation_grounds_feedback_in_learner_text() -> None:
    eval_b2 = _local_fallback_evaluation(
        WritingEvaluation,
        user_prompt=(
            '{"task_prompt": "Describe a project.", '
            '"learner_writing": "<learner_writing>Recently, I built an automated reporting dashboard using Python and SQL to track weekly team performance. This project mattered to me because it eliminated hours of repetitive manual data entry, giving my colleagues more time to focus on strategic work. Next, I would like to improve my data visualization skills while presenting complex trends clearly.</learner_writing>"}'
        ),
    )
    assert eval_b2.sufficient_evidence is True
    assert eval_b2.cefr_level in ("B1", "B2")
    assert any("automated" in s or "because" in s or "sentences" in s for s in eval_b2.strengths)

    eval_insufficient = _local_fallback_evaluation(
        WritingEvaluation,
        user_prompt='{"task_prompt": "Describe a project.", "learner_writing": "hello world"}',
    )
    assert eval_insufficient.sufficient_evidence is False
    assert eval_insufficient.reason == "INSUFFICIENT_EVIDENCE"


def test_langsmith_trace_redacts_learner_text_and_pii() -> None:
    from app.infrastructure.ai.tracing import (
        REDACTED_LEARNER_TEXT,
        REDACTED_PII,
        sanitize_trace_payload,
    )

    payload = {
        "prompt": "Prompt header\n<learner_writing>\nMy private essay\n</learner_writing>",
        "transcript": "My spoken recording transcript",
        "email": "learner@example.com",
        "nested": [{"text": "Draft essay"}],
    }
    sanitized = sanitize_trace_payload(payload)
    assert "My private essay" not in sanitized["prompt"]
    assert REDACTED_LEARNER_TEXT in sanitized["prompt"]
    assert sanitized["transcript"] == REDACTED_LEARNER_TEXT
    assert sanitized["email"] == REDACTED_PII
    assert sanitized["nested"][0]["text"] == REDACTED_PII or sanitized["nested"][0]["text"] == REDACTED_LEARNER_TEXT



