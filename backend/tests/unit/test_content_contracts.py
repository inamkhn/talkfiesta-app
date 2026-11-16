"""Unit tests for Phase 1 Content Factory contracts, B1 pilot blueprint, and validators."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.content.blueprint_loader import (
    get_day_blueprint,
    load_blueprint_manifest,
    load_cycle_blueprint,
)
from app.modules.content.contracts import (
    AiReviewReport,
    SpeakingLessonContract,
    VocabularyUnitOutput,
    WritingLessonContract,
    redact_for_learner,
)
from app.modules.content.validators import (
    validate_release_manifest,
    validate_speaking_lesson,
    validate_vocabulary_unit,
    validate_writing_lesson,
)


def _sample_vocab_unit() -> VocabularyUnitOutput:
    words = []
    word_keys = []
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
    for idx, lemma in enumerate(lemmas, start=1):
        key = f"B1-C1-D01-WORD-{idx:02d}"
        word_keys.append(key)
        words.append(
            {
                "item_key": key,
                "word": lemma,
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


def test_b1_pilot_blueprint_loads_all_21_days_and_bounded_context() -> None:
    manifest = load_blueprint_manifest()
    assert manifest.blueprint_version == "2026.11.1"
    cycle_bp = load_cycle_blueprint("B1", 1)
    assert len(cycle_bp.days) == 21

    ctx = get_day_blueprint("B1", 1, 5, goal_variant="BUSINESS")
    assert ctx.day == 5
    assert ctx.goal_variant == "BUSINESS"
    assert "remote" in ctx.goal_day_focus.lower()
    assert [s.day for s in ctx.prior_day_summaries] == [2, 3, 4]


def test_vocabulary_unit_passes_contracts_and_validators() -> None:
    unit = _sample_vocab_unit()
    day_bp = get_day_blueprint("B1", 1, 1).day_blueprint
    result = validate_vocabulary_unit(unit, day_bp)
    assert result.passed is True
    assert result.errors == []


def test_vocabulary_validator_rejects_duplicate_lemma_and_html() -> None:
    unit = _sample_vocab_unit()
    unit.words[1].lemma = "memorable"
    unit.words[0].definition = "<script>alert(1)</script>Bad content"
    day_bp = get_day_blueprint("B1", 1, 1).day_blueprint

    result = validate_vocabulary_unit(unit, day_bp)
    codes = {issue.code for issue in result.errors}
    assert "DUPLICATE_LEMMA" in codes
    assert "HTML_NOT_ALLOWED" in codes


def test_vocabulary_validator_rejects_bad_answer_key_and_dangling_ref() -> None:
    unit = _sample_vocab_unit()
    unit.lesson.exercises[0].correct_choice = "nonexistent"  # type: ignore[union-attr]
    unit.lesson.exercises[2].word_item_key = "B1-C1-D01-WORD-99"  # type: ignore[union-attr]
    day_bp = get_day_blueprint("B1", 1, 1).day_blueprint

    result = validate_vocabulary_unit(unit, day_bp)
    codes = {issue.code for issue in result.errors}
    assert "INVALID_ANSWER_KEY" in codes
    assert "DANGLING_WORD_REFERENCE" in codes


def test_speaking_and_writing_contracts_and_redaction() -> None:
    day_bp = get_day_blueprint("B1", 1, 1).day_blueprint
    speaking = SpeakingLessonContract.model_validate(
        {
            "item_key": "B1-C1-D01-SPEAKING-CORE",
            "theme": day_bp.theme,
            "learning_objective": day_bp.learning_objective,
            "description": "Speak about a memorable experience.",
            "exercise_type": "CONVERSATIONAL",
            "topic": "Memorable experiences",
            "title": "Tell me about a memorable experience",
            "prompt": "Describe an experience that you still remember clearly.",
            "instructions": "Organize your response into beginning, main event, and reflection.",
            "preparation_questions": ["When did it happen?", "Why did it matter?"],
            "target_duration_seconds": 60,
            "preparation_seconds": 15,
            "target_vocabulary": ["memorable", "accomplish"],
            "target_grammar": ["past simple"],
            "tips": ["Speak clearly.", "Use concrete details."],
            "learner_success_criteria": ["Clear sequence", "Explains significance"],
            "private_evaluation": {
                "rubric_version": "speaking-b1-v1",
                "criteria": ["grammar", "vocabulary", "coherence", "task_completion"],
                "sample_response": "Private model answer.",
            },
        }
    )
    assert validate_speaking_lesson(speaking, day_bp).passed is True

    writing = WritingLessonContract.model_validate(
        {
            "item_key": "B1-C1-D01-WRITING-CORE",
            "theme": day_bp.theme,
            "learning_objective": day_bp.learning_objective,
            "description": "Write a short narrative.",
            "writing_type": "NARRATIVE",
            "title": "A memory I will never forget",
            "prompt": "Write about an experience that shaped your perspective.",
            "instructions": "Include a clear beginning, middle, and ending.",
            "target_word_count": 80,
            "minimum_word_count": 40,
            "maximum_word_count": 180,
            "time_limit_minutes": 15,
            "target_grammar": ["past simple", "past continuous"],
            "target_vocabulary": ["memorable", "milestone"],
            "structure_guidance": ["Set the scene", "Reflect on the outcome"],
            "tips": ["Check past tense verbs.", "Use transition words."],
            "learner_success_criteria": ["Clear timeline", "Relevant details"],
            "private_evaluation": {
                "rubric_version": "writing-b1-v1",
                "criteria": ["grammar", "vocabulary", "coherence", "task_completion"],
                "sample_response": "Private essay sample.",
            },
        }
    )
    assert validate_writing_lesson(writing, day_bp).passed is True

    unit_public = redact_for_learner(_sample_vocab_unit().lesson.model_dump(mode="json"))
    assert "private_evaluation" not in unit_public
    for ex in unit_public["exercises"]:
        assert "correct_choice" not in ex
        assert "correct_choice_id" not in ex

    with pytest.raises(ValidationError):
        WritingLessonContract.model_validate(
            {
                **writing.model_dump(mode="json"),
                "minimum_word_count": 120,
                "target_word_count": 80,
            }
        )


def test_release_manifest_blocks_partial_and_passes_complete_release() -> None:
    reviewer = uuid4()
    partial_items = [
        {
            "id": str(uuid4()),
            "kind": "SPEAKING_LESSON",
            "slot": "CORE",
            "day": d,
            "status": "REVIEW",
            "reviewed_by": reviewer,
            "body": {},
        }
        for d in range(1, 6)
    ]
    partial_res = validate_release_manifest(partial_items, module="SPEAKING")
    assert partial_res.passed is False
    assert any(i.code == "MISSING_DAY" for i in partial_res.errors)

    complete_items = [
        {
            "id": str(uuid4()),
            "kind": "SPEAKING_LESSON",
            "slot": "CORE",
            "day": d,
            "status": "REVIEW",
            "reviewed_by": reviewer,
            "body": {},
        }
        for d in range(1, 22)
    ]
    assert validate_release_manifest(complete_items, module="SPEAKING").passed is True


def test_ai_review_report_threshold() -> None:
    passing = AiReviewReport.model_validate(
        {
            "overall_decision": "PASS_TO_HUMAN_REVIEW",
            "scores": {
                "cefr_fit": 4,
                "objective_alignment": 5,
                "language_correctness": 5,
                "clarity": 4,
                "pedagogical_value": 4,
                "progression_and_uniqueness": 4,
                "exercise_validity": 5,
            },
            "critical_issues": [],
            "warnings": [],
            "recommended_action": "Send to human review queue.",
        }
    )
    assert passing.meets_auto_review_bar() is True

