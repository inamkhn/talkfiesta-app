"""Deterministic selection of complete, published first-cycle curriculum."""

from uuid import UUID

from app.core.exceptions import ServiceUnavailableError
from app.modules.content.models import ContentItem
from app.modules.onboarding.repository import OnboardingRepository

MODULES = ("SPEAKING", "VOCABULARY", "WRITING")


async def select_curriculum(
    repository: OnboardingRepository,
    cefr: str,
    goals: list[str],
) -> dict[str, tuple[str, str]]:
    variants = list(
        dict.fromkeys(
            ["GENERAL" if goal == "FLUENCY" else goal for goal in goals] + ["GENERAL"]
        )
    )
    items = await repository.curriculum(cefr, variants)
    groups: dict[tuple[str, str, str], list[ContentItem]] = {}
    for item in items:
        if item.module in MODULES and item.kind == f"{item.module}_LESSON":
            groups.setdefault(
                (item.module, item.goal_variant, item.release_key), []
            ).append(item)
    selected: dict[str, tuple[str, str]] = {}
    for module in MODULES:
        for variant in variants:
            for (group_module, group_variant, release), lessons in groups.items():
                if (group_module, group_variant) != (module, variant):
                    continue
                if len(lessons) != 21 or {lesson.day for lesson in lessons} != set(
                    range(1, 22)
                ):
                    continue
                if module == "VOCABULARY":
                    word_ids: set[UUID] = set()
                    valid = True
                    for lesson in lessons:
                        refs = (
                            lesson.body.get("word_content_ids")
                            if isinstance(lesson.body, dict)
                            else None
                        )
                        if not isinstance(refs, list) or len(refs) != 10:
                            valid = False
                            break
                        try:
                            ids = {UUID(ref) for ref in refs if isinstance(ref, str)}
                        except ValueError:
                            valid = False
                            break
                        if len(ids) != 10:
                            valid = False
                            break
                        word_ids.update(ids)
                    if (
                        not valid
                        or await repository.published_words(word_ids) != word_ids
                    ):
                        continue
                selected[module] = (release, variant)
                break
            if module in selected:
                break
        if module not in selected:
            raise ServiceUnavailableError(
                f"A complete published {module.lower()} curriculum is not available for this placement.",
                code="CURRICULUM_UNAVAILABLE",
            )
    return selected
