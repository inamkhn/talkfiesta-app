"""Placement-bank v1: objective coverage plus writing and optional speech."""

from collections import Counter

from app.core.exceptions import ServiceUnavailableError
from app.modules.content.models import ContentItem

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


def validate_bank(items: list[ContentItem]) -> None:
    """Require usable published questions, never returning private answer keys.

    Initial blueprint: one MCQ per grammar/vocabulary skill and CEFR band,
    plus one writing and one optional speaking prompt. Selection may draw a
    subset adaptively; future selection must use this same body contract.
    """
    coverage: Counter = Counter()
    for item in items:
        body = item.body
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("prompt"), str)
            or not body["prompt"].strip()
        ):
            continue
        kind, skill = body.get("kind"), body.get("skill")
        if kind == "MULTIPLE_CHOICE" and skill in ("GRAMMAR", "VOCABULARY"):
            choices = body.get("choices")
            if not isinstance(choices, list) or not 2 <= len(choices) <= 6:
                continue
            if any(
                not isinstance(c, dict)
                or not isinstance(c.get("id"), str)
                or not c["id"]
                or not isinstance(c.get("text"), str)
                or not c["text"].strip()
                for c in choices
            ):
                continue
            ids = [choice["id"] for choice in choices]
            if len(set(ids)) != len(ids) or body.get("correct_choice_id") not in ids:
                continue
            if item.cefr_level in LEVELS:
                coverage[(skill, item.cefr_level)] += 1
        elif (kind, skill) in (
            ("SHORT_WRITING", "WRITING"),
            ("RECORDED_SPEAKING", "SPEAKING"),
        ):
            if isinstance(body.get("rubric"), dict) and body["rubric"]:
                coverage[skill] += 1
    if (
        any(
            not coverage[(skill, level)]
            for skill in ("GRAMMAR", "VOCABULARY")
            for level in LEVELS
        )
        or not coverage["WRITING"]
        or not coverage["SPEAKING"]
    ):
        raise ServiceUnavailableError(
            "The configured assessment question bank is incomplete or unavailable.",
            code="ASSESSMENT_CONTENT_UNAVAILABLE",
        )
