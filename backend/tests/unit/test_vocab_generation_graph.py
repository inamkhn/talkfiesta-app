"""Unit tests for Phase 3 Vocabulary prompts, LangGraph workflow, and persistence helpers."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.modules.content.ai.persistence import resolve_vocab_lesson_body
from app.modules.content.ai.vocab_graph import build_vocab_generation_graph
from app.modules.content.blueprint_loader import get_day_blueprint
from app.modules.content.contracts import AiReviewReport, VocabularyUnitOutput
from app.modules.content.prompt_loader import (
    load_generator_prompt,
    load_reviewer_prompt,
)


def _sample_vocab_unit(*, duplicate_lemma: bool = False) -> VocabularyUnitOutput:
    lemmas = [
        "memorable",
        "accomplish",
        "reflect",
        "milestone",
        "challenge",
        "resilient",
        "perspective",
        "vivid",
        "grateful",
        "turning",
    ]
    if duplicate_lemma:
        lemmas[1] = lemmas[0]

    words = []
    word_keys = []
    for idx, lemma in enumerate(lemmas, start=1):
        key = f"B1-C1-D01-WORD-{idx:02d}"
        word_keys.append(key)
        words.append(
            {
                "item_key": key,
                "word": f"{lemma}_{idx}" if duplicate_lemma and idx == 2 else lemma,
                "lemma": lemma,
                "part_of_speech": "adjective" if idx in (1, 6, 8, 9) else "noun",
                "cefr_level": "B1",
                "definition": f"Meaning of {lemma} in everyday B1 contexts.",
                "ipa": None,
                "examples": [f"This {lemma} moment taught us something important."],
                "collocations": [f"{lemma} experience"],
                "synonyms": [],
                "antonyms": [],
                "common_mistakes": [],
                "review_exercise": {
                    "prompt": f"Which definition best matches '{lemma}'?",
                    "choices": [
                        {"id": "a", "text": f"Meaning of {lemma} in everyday B1 contexts."},
                        {"id": "b", "text": "An unrelated distractor option."},
                        {"id": "c", "text": "Another unrelated distractor option."},
                    ],
                    "correct_choice_id": "a",
                },
            }
        )

    return VocabularyUnitOutput.model_validate(
        {
            "lesson": {
                "item_key": "B1-C1-D01-VOCAB-CORE",
                "theme": "Memorable experiences",
                "learning_objective": "Describe a past experience and explain why it was important.",
                "description": "Learn 10 B1 words for describing memorable experiences.",
                "instructions": "Study the words, then complete each exercise.",
                "estimated_minutes": 10,
                "word_item_keys": word_keys,
                "exercises": [
                    {
                        "item_id": "EX-01",
                        "type": "FILL_BLANK",
                        "prompt": "It was a ___ experience that I will never forget.",
                        "choices": ["memorable", "vivid", "grateful", "resilient"],
                        "correct_choice": "memorable",
                    },
                    {
                        "item_id": "EX-02",
                        "type": "MATCH_DEFINITION",
                        "prompt": "Select the definition that matches 'accomplish':",
                        "choices": [
                            {"id": "a", "text": "To succeed in finishing something."},
                            {"id": "b", "text": "To forget an important date."},
                            {"id": "c", "text": "To delay a decision."},
                        ],
                        "correct_choice_id": "a",
                    },
                    {
                        "item_id": "EX-03",
                        "type": "USE_IN_CONTEXT",
                        "word_item_key": word_keys[2],
                        "prompt": "Write one complete sentence using the word 'reflect'.",
                    },
                ],
                "private_evaluation": {
                    "rubric_version": "vocab-b1-v1",
                    "criteria": ["accurate meaning", "natural collocation"],
                    "explanations": {"EX-01": "Memorable means worth remembering."},
                },
            },
            "words": words,
        }
    )


def _sample_review_report(
    *,
    decision: str = "PASS_TO_HUMAN_REVIEW",
    score: int = 5,
    critical_issues: list[str] | None = None,
) -> AiReviewReport:
    return AiReviewReport.model_validate(
        {
            "overall_decision": decision,
            "scores": {
                "cefr_fit": score,
                "objective_alignment": score,
                "language_correctness": score,
                "clarity": score,
                "pedagogical_value": score,
                "progression_and_uniqueness": score,
                "exercise_validity": score,
            },
            "critical_issues": critical_issues or [],
            "warnings": [],
            "recommended_action": "Ready for editorial review."
            if decision == "PASS_TO_HUMAN_REVIEW"
            else "Regenerate with feedback.",
        }
    )


def test_prompt_loader_combines_common_and_vocabulary_prompts() -> None:
    gen_version, gen_prompt = load_generator_prompt("VOCABULARY")
    rev_version, rev_prompt = load_reviewer_prompt("VOCABULARY")

    assert gen_version == "vocabulary-generate-v1"
    assert rev_version == "vocabulary-review-v1"
    assert "TalkFiesta" in gen_prompt
    assert "Vocabulary" in gen_prompt
    assert "AI Quality Reviewer" in rev_prompt


def test_vocab_graph_happy_path_passes_to_review(monkeypatch) -> None:
    stages: list[str] = []

    def fake_invoke(schema, *, system_prompt, user_prompt, runnable_config=None):
        if schema is VocabularyUnitOutput:
            return _sample_vocab_unit()
        if schema is AiReviewReport:
            return _sample_review_report()
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(
        "app.modules.content.ai.vocab_graph.invoke_structured_model",
        fake_invoke,
    )

    graph = build_vocab_generation_graph()
    result = graph.invoke(
        {
            "job_id": "job-1",
            "generation_batch_key": "batch-1",
            "release_key": "B1-C1-V1",
            "prompt_bundle_version": "content-factory-v1",
            "context": get_day_blueprint("B1", 1, 1),
            "prior_words": [],
            "retry_count": 0,
            "max_retries": 2,
            "report_stage": stages.append,
        }
    )

    assert result["outcome"] == "PASS_TO_REVIEW"
    assert result["validation_errors"] == []
    assert result["unit"] is not None
    assert result["review_report"] is not None
    assert stages == ["GENERATING_CONTENT", "VALIDATING_CONTENT", "REVIEWING_QUALITY"]


def test_vocab_graph_retries_on_validation_error_and_succeeds(monkeypatch) -> None:
    gen_calls = 0

    def fake_invoke(schema, *, system_prompt, user_prompt, runnable_config=None):
        nonlocal gen_calls
        if schema is VocabularyUnitOutput:
            gen_calls += 1
            return _sample_vocab_unit(duplicate_lemma=(gen_calls == 1))
        if schema is AiReviewReport:
            return _sample_review_report()
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(
        "app.modules.content.ai.vocab_graph.invoke_structured_model",
        fake_invoke,
    )

    graph = build_vocab_generation_graph()
    result = graph.invoke(
        {
            "job_id": "job-2",
            "generation_batch_key": "batch-1",
            "release_key": "B1-C1-V1",
            "prompt_bundle_version": "content-factory-v1",
            "context": get_day_blueprint("B1", 1, 1),
            "prior_words": [],
            "retry_count": 0,
            "max_retries": 2,
            "report_stage": None,
        }
    )

    assert gen_calls == 2
    assert result["retry_count"] == 1
    assert result["outcome"] == "PASS_TO_REVIEW"


def test_vocab_graph_retries_when_reviewer_requests_regenerate(monkeypatch) -> None:
    rev_calls = 0

    def fake_invoke(schema, *, system_prompt, user_prompt, runnable_config=None):
        nonlocal rev_calls
        if schema is VocabularyUnitOutput:
            return _sample_vocab_unit()
        if schema is AiReviewReport:
            rev_calls += 1
            if rev_calls == 1:
                return _sample_review_report(
                    decision="REGENERATE",
                    score=3,
                    critical_issues=["Example sentences are too repetitive."],
                )
            return _sample_review_report(decision="PASS_TO_HUMAN_REVIEW", score=5)
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(
        "app.modules.content.ai.vocab_graph.invoke_structured_model",
        fake_invoke,
    )

    graph = build_vocab_generation_graph()
    result = graph.invoke(
        {
            "job_id": "job-3",
            "generation_batch_key": "batch-1",
            "release_key": "B1-C1-V1",
            "prompt_bundle_version": "content-factory-v1",
            "context": get_day_blueprint("B1", 1, 1),
            "prior_words": [],
            "retry_count": 0,
            "max_retries": 2,
            "report_stage": None,
        }
    )

    assert rev_calls == 2
    assert result["retry_count"] == 1
    assert result["outcome"] == "PASS_TO_REVIEW"


def test_vocab_graph_fails_when_validation_retries_exhausted(monkeypatch) -> None:
    def fake_invoke(schema, *, system_prompt, user_prompt, runnable_config=None):
        if schema is VocabularyUnitOutput:
            return _sample_vocab_unit(duplicate_lemma=True)
        raise AssertionError("Reviewer should not run when validation fails.")

    monkeypatch.setattr(
        "app.modules.content.ai.vocab_graph.invoke_structured_model",
        fake_invoke,
    )

    graph = build_vocab_generation_graph()
    result = graph.invoke(
        {
            "job_id": "job-4",
            "generation_batch_key": "batch-1",
            "release_key": "B1-C1-V1",
            "prompt_bundle_version": "content-factory-v1",
            "context": get_day_blueprint("B1", 1, 1),
            "prior_words": [],
            "retry_count": 0,
            "max_retries": 1,
            "report_stage": None,
        }
    )

    assert result["outcome"] == "FAILED"
    assert result["retry_count"] == 1
    assert result["validation_errors"]


def test_resolve_vocab_lesson_body_populates_uuids() -> None:
    unit = _sample_vocab_unit()
    key_to_id: dict[str, UUID] = {
        key: uuid4() for key in unit.lesson.word_item_keys
    }

    body = resolve_vocab_lesson_body(unit, key_to_id)

    assert body["word_content_ids"] == [
        str(key_to_id[key]) for key in unit.lesson.word_item_keys
    ]
    use_in_context = [
        ex for ex in body["exercises"] if ex["type"] == "USE_IN_CONTEXT"
    ]
    assert len(use_in_context) == 1
    expected_word_key = unit.lesson.word_item_keys[2]
    assert use_in_context[0]["word_id"] == str(key_to_id[expected_word_key])


def test_vocab_graph_preserves_and_uses_custom_invoke_model(monkeypatch) -> None:
    def fail_default(*args, **kwargs):
        raise AssertionError("Default invoke_structured_model should not be called.")

    monkeypatch.setattr(
        "app.modules.content.ai.vocab_graph.invoke_structured_model",
        fail_default,
    )

    calls: list[type] = []

    def custom_invoke(schema, *, system_prompt, user_prompt, runnable_config=None):
        calls.append(schema)
        if schema is VocabularyUnitOutput:
            return _sample_vocab_unit()
        if schema is AiReviewReport:
            return _sample_review_report()
        raise AssertionError(f"Unexpected schema: {schema}")

    graph = build_vocab_generation_graph()
    result = graph.invoke(
        {
            "job_id": "job-custom-model",
            "generation_batch_key": "batch-1",
            "release_key": "B1-C1-V1",
            "prompt_bundle_version": "content-factory-v1",
            "context": get_day_blueprint("B1", 1, 1),
            "prior_words": [],
            "retry_count": 0,
            "max_retries": 2,
            "report_stage": None,
            "invoke_model": custom_invoke,
        }
    )

    assert result["outcome"] == "PASS_TO_REVIEW"
    assert calls == [VocabularyUnitOutput, AiReviewReport]


