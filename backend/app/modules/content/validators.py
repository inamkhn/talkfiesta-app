"""Deterministic hard validators for generated curriculum units and release manifests."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.modules.content.blueprint_loader import DayBlueprint
from app.modules.content.contracts import (
    FillBlankExerciseContract,
    MatchDefinitionExerciseContract,
    SpeakingLessonContract,
    UseInContextExerciseContract,
    VocabularyUnitOutput,
    WritingLessonContract,
)

_HTML_OR_SCRIPT_RE = re.compile(
    r"<\s*(?:script|iframe|object|embed|style|svg|img|a|div|span|p)\b|javascript:",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: Literal["ERROR", "WARNING"]
    code: str
    field: str
    message: str


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "ERROR" for issue in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "ERROR"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "WARNING"]

    def add_error(self, code: str, field_name: str, message: str) -> None:
        self.issues.append(
            ValidationIssue(
                severity="ERROR", code=code, field=field_name, message=message
            )
        )

    def add_warning(self, code: str, field_name: str, message: str) -> None:
        self.issues.append(
            ValidationIssue(
                severity="WARNING", code=code, field=field_name, message=message
            )
        )


def _scan_for_html(obj: object, path: str, result: ValidationResult) -> None:
    if isinstance(obj, str):
        if _HTML_OR_SCRIPT_RE.search(obj):
            result.add_error(
                "HTML_NOT_ALLOWED",
                path,
                "Generated content must not contain HTML tags or script URIs.",
            )
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _scan_for_html(item, f"{path}[{idx}]", result)
    elif isinstance(obj, dict):
        for key, val in obj.items():
            _scan_for_html(val, f"{path}.{key}", result)


def validate_vocabulary_unit(
    unit: VocabularyUnitOutput,
    blueprint: DayBlueprint,
    *,
    prior_words: set[str] | None = None,
) -> ValidationResult:
    """Run deterministic hard rules on a generated 10-word vocabulary day unit."""
    result = ValidationResult()
    _scan_for_html(unit.model_dump(mode="json"), "vocabulary_unit", result)

    expected_count = blueprint.vocabulary_theme.target_count
    if len(unit.words) != expected_count:
        result.add_error(
            "WORD_COUNT_MISMATCH",
            "words",
            f"Expected {expected_count} words, found {len(unit.words)}.",
        )

    word_keys = [w.item_key for w in unit.words]
    if len(set(word_keys)) != len(word_keys):
        result.add_error(
            "DUPLICATE_ITEM_KEY",
            "words.item_key",
            "Word item_keys must be unique within the unit.",
        )

    lemmas = [w.lemma.lower().strip() for w in unit.words]
    if len(set(lemmas)) != len(lemmas):
        result.add_error(
            "DUPLICATE_LEMMA",
            "words.lemma",
            "Vocabulary unit contains duplicate word lemmas.",
        )

    word_key_set = set(word_keys)
    lesson_keys = unit.lesson.word_item_keys
    if len(lesson_keys) != expected_count or set(lesson_keys) != word_key_set:
        result.add_error(
            "DANGLING_WORD_REFERENCE",
            "lesson.word_item_keys",
            "lesson.word_item_keys must match the 10 generated VOCAB_WORD item_keys.",
        )

    if unit.lesson.item_key in word_key_set:
        result.add_error(
            "DUPLICATE_ITEM_KEY",
            "lesson.item_key",
            "Lesson item_key must not collide with any word item_key.",
        )

    exercise_ids = [ex.item_id for ex in unit.lesson.exercises]
    if len(set(exercise_ids)) != len(exercise_ids):
        result.add_error(
            "DUPLICATE_EXERCISE_ID",
            "lesson.exercises",
            "Exercise item_ids must be unique within the lesson.",
        )

    for idx, ex in enumerate(unit.lesson.exercises):
        if isinstance(ex, FillBlankExerciseContract):
            if "___" not in ex.prompt and "______" not in ex.prompt:
                result.add_error(
                    "MISSING_BLANK_MARKER",
                    f"lesson.exercises[{idx}].prompt",
                    "FILL_BLANK prompt must include '___' blank placeholder.",
                )
            if ex.correct_choice not in ex.choices:
                result.add_error(
                    "INVALID_ANSWER_KEY",
                    f"lesson.exercises[{idx}].correct_choice",
                    f"correct_choice {ex.correct_choice!r} is not in choices.",
                )
        elif isinstance(ex, MatchDefinitionExerciseContract):
            option_ids = {c.id for c in ex.choices}
            if ex.correct_choice_id not in option_ids:
                result.add_error(
                    "INVALID_ANSWER_KEY",
                    f"lesson.exercises[{idx}].correct_choice_id",
                    f"correct_choice_id {ex.correct_choice_id!r} not in choice IDs.",
                )
        elif isinstance(ex, UseInContextExerciseContract):
            if ex.word_item_key is not None and ex.word_item_key not in word_key_set:
                result.add_error(
                    "DANGLING_WORD_REFERENCE",
                    f"lesson.exercises[{idx}].word_item_key",
                    f"Referenced word_item_key {ex.word_item_key!r} does not exist in unit.words.",
                )

    avoid_set = {w.lower().strip() for w in blueprint.vocabulary_theme.avoid}
    prior_lower = {w.lower().strip() for w in (prior_words or set())}
    for w in unit.words:
        lowered = w.lemma.lower().strip()
        if lowered in avoid_set:
            result.add_warning(
                "AVOID_LIST_MATCH",
                f"words.{w.item_key}",
                f"Word {w.word!r} appears in the blueprint avoid list.",
            )
        if lowered in prior_lower:
            result.add_warning(
                "PRIOR_DAY_REUSE",
                f"words.{w.item_key}",
                f"Word {w.word!r} already appeared earlier in this cycle.",
            )

    return result


def validate_speaking_lesson(
    lesson: SpeakingLessonContract,
    blueprint: DayBlueprint,
) -> ValidationResult:
    """Run deterministic hard checks on a generated speaking lesson."""
    result = ValidationResult()
    _scan_for_html(lesson.model_dump(mode="json"), "speaking_lesson", result)

    if lesson.exercise_type != blueprint.speaking.exercise_type:
        result.add_error(
            "EXERCISE_TYPE_MISMATCH",
            "exercise_type",
            f"Expected {blueprint.speaking.exercise_type}, got {lesson.exercise_type}.",
        )
    if lesson.target_duration_seconds != blueprint.speaking.target_duration_seconds:
        result.add_warning(
            "DURATION_DRIFT",
            "target_duration_seconds",
            f"Blueprint targets {blueprint.speaking.target_duration_seconds}s, got {lesson.target_duration_seconds}s.",
        )
    return result


def validate_writing_lesson(
    lesson: WritingLessonContract,
    blueprint: DayBlueprint,
) -> ValidationResult:
    """Run deterministic hard checks on a generated writing lesson."""
    result = ValidationResult()
    _scan_for_html(lesson.model_dump(mode="json"), "writing_lesson", result)

    if lesson.writing_type != blueprint.writing.writing_type:
        result.add_error(
            "WRITING_TYPE_MISMATCH",
            "writing_type",
            f"Expected {blueprint.writing.writing_type}, got {lesson.writing_type}.",
        )
    if (
        lesson.minimum_word_count < blueprint.writing.minimum_word_count - 10
        or lesson.maximum_word_count > blueprint.writing.maximum_word_count + 50
    ):
        result.add_warning(
            "WORD_COUNT_DRIFT",
            "minimum_word_count",
            "Writing word bounds drifted noticeably from the blueprint.",
        )
    return result


def validate_release_manifest(
    items: list[dict],
    *,
    module: Literal["VOCABULARY", "SPEAKING", "WRITING"],
    expected_days: int = 21,
) -> ValidationResult:
    """Verify a module release is complete, approved, and free of duplicates before publishing."""
    result = ValidationResult()
    expected_kind = f"{module}_LESSON"
    core_days: dict[int, list[dict]] = {}
    vocab_word_ids: set[str] = set()
    approved_word_ids: set[str] = set()

    for item in items:
        kind = item.get("kind")
        status = item.get("status")
        reviewed_by = item.get("reviewed_by")
        is_approved = status == "PUBLISHED" or (
            status == "REVIEW" and reviewed_by is not None
        )

        if kind == "VOCAB_WORD":
            item_id = str(item.get("id"))
            vocab_word_ids.add(item_id)
            if is_approved:
                approved_word_ids.add(item_id)
            continue

        if kind == expected_kind and item.get("slot") == "CORE":
            day = item.get("day")
            if isinstance(day, int):
                core_days.setdefault(day, []).append(item)
            if not is_approved:
                result.add_error(
                    "UNAPPROVED_LESSON",
                    f"day_{day}",
                    f"Day {day} lesson is not approved for publication.",
                )

    for day in range(1, expected_days + 1):
        day_items = core_days.get(day, [])
        if not day_items:
            result.add_error(
                "MISSING_DAY",
                f"day_{day}",
                f"Missing CORE {expected_kind} for day {day}.",
            )
        elif len(day_items) > 1:
            result.add_error(
                "DUPLICATE_CORE_LESSON",
                f"day_{day}",
                f"Found {len(day_items)} CORE lessons for day {day}.",
            )
        elif module == "VOCABULARY":
            body = day_items[0].get("body") or {}
            word_ids = body.get("word_content_ids") or []
            if len(word_ids) != 10 or len(set(word_ids)) != 10:
                result.add_error(
                    "INVALID_VOCAB_WORD_COUNT",
                    f"day_{day}.word_content_ids",
                    f"Day {day} vocabulary lesson must reference 10 distinct words.",
                )
            else:
                for wid in word_ids:
                    wid_str = str(wid)
                    if wid_str not in vocab_word_ids:
                        result.add_error(
                            "MISSING_WORD_REFERENCE",
                            f"day_{day}.word_content_ids",
                            f"Day {day} references missing VOCAB_WORD {wid_str}.",
                        )
                    elif wid_str not in approved_word_ids:
                        result.add_error(
                            "UNAPPROVED_WORD_REFERENCE",
                            f"day_{day}.word_content_ids",
                            f"Day {day} references unapproved VOCAB_WORD {wid_str}.",
                        )

    return result

