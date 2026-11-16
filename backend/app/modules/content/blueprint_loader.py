"""Version-controlled curriculum blueprint loader and bounded context resolver."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.content.contracts import (
    CefrLevel,
    GoalVariant,
    SpeakingExerciseType,
    WritingType,
)

BLUEPRINTS_DIR = Path(__file__).resolve().parent / "blueprints"


class BlueprintModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BlueprintManifest(BlueprintModel):
    blueprint_version: str
    supported_levels: list[CefrLevel]
    supported_cycles: list[int]
    supported_modules: list[str]
    supported_goal_variants: list[GoalVariant]
    pilot: dict[str, object]


class VocabularyThemeConfig(BlueprintModel):
    topic: str
    target_count: int = Field(default=10, ge=5, le=20)
    avoid: list[str] = Field(default_factory=list)


class SpeakingBlueprintConfig(BlueprintModel):
    exercise_type: SpeakingExerciseType
    target_duration_seconds: int = Field(ge=20, le=180)
    preparation_seconds: int = Field(ge=5, le=60)


class WritingBlueprintConfig(BlueprintModel):
    writing_type: WritingType
    target_word_count: int = Field(ge=25, le=400)
    minimum_word_count: int = Field(ge=15, le=300)
    maximum_word_count: int = Field(ge=40, le=600)
    time_limit_minutes: int = Field(ge=5, le=45)


class DayBlueprint(BlueprintModel):
    day: int = Field(ge=1, le=21)
    theme: str
    learning_objective: str
    prerequisites: list[str] = Field(default_factory=list)
    grammar_focus: list[str] = Field(min_length=1)
    vocabulary_theme: VocabularyThemeConfig
    speaking: SpeakingBlueprintConfig
    writing: WritingBlueprintConfig
    avoid_repeating: list[str] = Field(default_factory=list)
    goal_variant_rules: dict[GoalVariant, str]


class CycleBlueprint(BlueprintModel):
    blueprint_version: str
    cefr_level: CefrLevel
    cycle: int = Field(ge=1, le=5)
    title: str
    days: list[DayBlueprint] = Field(min_length=1, max_length=21)

    @model_validator(mode="after")
    def validate_unique_days(self):
        day_numbers = [d.day for d in self.days]
        if len(set(day_numbers)) != len(day_numbers):
            raise ValueError("Cycle blueprint cannot contain duplicate day numbers.")
        return self


class GoalVariantRule(BlueprintModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    label: str
    context_guidance: str
    language_register: str = Field(alias="register")


class PriorDaySummary(BlueprintModel):
    day: int
    theme: str
    learning_objective: str


class ResolvedDayContext(BlueprintModel):
    """Bounded context package passed to one module-day generation unit."""

    blueprint_version: str
    cefr_level: CefrLevel
    cycle: int
    day: int
    goal_variant: GoalVariant
    goal_guidance: GoalVariantRule
    goal_day_focus: str
    day_blueprint: DayBlueprint
    content_rules: dict[str, object]
    prior_day_summaries: list[PriorDaySummary] = Field(default_factory=list)


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Blueprint file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Blueprint YAML must be a mapping: {path}")
    return data


@lru_cache(maxsize=8)
def load_blueprint_manifest() -> BlueprintManifest:
    return BlueprintManifest.model_validate(
        _read_yaml(BLUEPRINTS_DIR / "blueprint_version.yaml")
    )


@lru_cache(maxsize=8)
def load_goal_variants() -> dict[GoalVariant, GoalVariantRule]:
    raw = _read_yaml(BLUEPRINTS_DIR / "shared" / "goal_variants.yaml")
    return {
        key: GoalVariantRule.model_validate(val)  # type: ignore[misc]
        for key, val in raw.items()
    }


@lru_cache(maxsize=8)
def load_content_rules() -> dict[str, object]:
    return _read_yaml(BLUEPRINTS_DIR / "shared" / "content_rules.yaml")


@lru_cache(maxsize=32)
def load_cycle_blueprint(
    cefr_level: CefrLevel,
    cycle: int,
    blueprint_version: str | None = None,
) -> CycleBlueprint:
    manifest = load_blueprint_manifest()
    if (
        blueprint_version is not None
        and blueprint_version != manifest.blueprint_version
    ):
        raise ValueError(
            f"Unsupported blueprint_version={blueprint_version!r}; "
            f"expected {manifest.blueprint_version!r}."
        )
    path = BLUEPRINTS_DIR / "cefr" / cefr_level / f"cycle_{cycle}.yaml"
    bp = CycleBlueprint.model_validate(_read_yaml(path))
    if bp.cefr_level != cefr_level or bp.cycle != cycle:
        raise ValueError(
            f"Blueprint metadata mismatch in {path}: expected {cefr_level} C{cycle}."
        )
    return bp


def get_day_blueprint(
    cefr_level: CefrLevel,
    cycle: int,
    day: int,
    *,
    goal_variant: GoalVariant = "GENERAL",
    blueprint_version: str | None = None,
    prior_window: int = 3,
) -> ResolvedDayContext:
    """Resolve one day's blueprint plus bounded prior-day summaries."""
    cycle_bp = load_cycle_blueprint(cefr_level, cycle, blueprint_version)
    day_map = {d.day: d for d in cycle_bp.days}
    day_bp = day_map.get(day)
    if day_bp is None:
        raise KeyError(
            f"Day {day} not found in blueprint {cefr_level} cycle {cycle}."
        )

    goal_variants = load_goal_variants()
    goal_guidance = goal_variants[goal_variant]
    goal_day_focus = day_bp.goal_variant_rules.get(
        goal_variant, goal_guidance.context_guidance
    )

    prior_summaries = [
        PriorDaySummary(
            day=d_num,
            theme=day_map[d_num].theme,
            learning_objective=day_map[d_num].learning_objective,
        )
        for d_num in range(max(1, day - prior_window), day)
        if d_num in day_map
    ]

    return ResolvedDayContext(
        blueprint_version=cycle_bp.blueprint_version,
        cefr_level=cefr_level,
        cycle=cycle,
        day=day,
        goal_variant=goal_variant,
        goal_guidance=goal_guidance,
        goal_day_focus=goal_day_focus,
        day_blueprint=day_bp,
        content_rules=load_content_rules(),
        prior_day_summaries=prior_summaries,
    )
