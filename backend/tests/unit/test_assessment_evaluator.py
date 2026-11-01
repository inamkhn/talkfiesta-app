"""Unit tests for the initial assessment evaluator, LangGraph workflow, and placement policy."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.assessment.ai.evaluators import evaluate_assessment
from app.modules.assessment.ai.state import (
    FrozenAssessment,
    FrozenSpeakingEvidence,
    FrozenWritingEvidence,
    StructuredLanguageEvaluation,
)
from app.modules.assessment.placement_policy import (
    EvaluatedSkillFeedback,
    ObjectiveItemOutcome,
    assign_provisional_cefr,
)


def _sample_objective(levels_and_correct: list[tuple[str, bool]]) -> list[ObjectiveItemOutcome]:
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
    assert placement.confidence == "MEDIUM"
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


def test_evaluate_assessment_graph_with_speaking_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()
    frozen = FrozenAssessment(
        job_id=job_id,
        attempt_id=uuid4(),
        user_id=uuid4(),
        grammar_outcomes=_sample_objective(
            [("A2", True), ("B1", True), ("B2", False), ("B1", True)]
        ),
        vocabulary_outcomes=_sample_objective(
            [("A2", True), ("B1", True), ("B2", True), ("C1", False)]
        ),
        writing=FrozenWritingEvidence(
            prompt="Write about your workday.",
            rubric={"criteria": ["grammar", "coherence"]},
            text="Yesterday I worked on the backend API and deployed a new service.",
        ),
        speaking=FrozenSpeakingEvidence(
            skipped=False,
            prompt="Describe your favorite travel memory.",
            rubric={"criteria": ["fluency", "vocabulary"]},
            object_key="assessment-audio/abc",
            content_type="audio/webm",
            size_bytes=1024,
            checksum_sha256="dummy",
        ),
    )

    monkeypatch.setattr(
        "app.modules.assessment.ai.evaluators.load_frozen_assessment",
        lambda _job_id: frozen,
    )
    monkeypatch.setattr(
        "app.modules.assessment.ai.nodes.read_audio",
        lambda *_args: b"fake-audio-bytes",
    )
    monkeypatch.setattr(
        "app.modules.assessment.ai.nodes.transcribe_audio_bytes",
        lambda *_args: "I traveled to Spain last summer and explored historic cities.",
    )
    monkeypatch.setattr(
        "app.modules.assessment.ai.nodes.invoke_structured_model",
        lambda _schema, **_kwargs: StructuredLanguageEvaluation(
            cefr_level="B1",
            sufficient_evidence=True,
            strengths=["Good narrative flow"],
            improvement_priorities=["Expand complex clause usage"],
        ),
    )

    stages: list[str] = []
    result = evaluate_assessment(job_id, stages.append)

    assert stages == [
        "TRANSCRIBING_AUDIO",
        "EVALUATING_LANGUAGE",
        "EVALUATING_LANGUAGE",
        "DETERMINING_PLACEMENT",
    ]
    assert result.cefr == "B1"
    assert result.confidence == "HIGH"
    assert result.skills.speaking.assessed is True
    assert result.skills.speaking.level == "B1"
    assert result.skills.writing.assessed is True
    assert result.skills.writing.level == "B1"
    assert result._langsmith_run_id is not None
    assert "_langsmith_run_id" not in result.model_dump()


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
    assert sanitized["nested"][0]["text"] == REDACTED_LEARNER_TEXT


