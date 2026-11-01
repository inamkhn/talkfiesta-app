"""Validated onboarding preferences and frontend routing contracts."""

from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, TypeAdapter

OnboardingStatus = Literal[
    "NOT_STARTED", "PREFERENCES_SAVED", "ASSESSING", "RESULT_READY", "COMPLETED"
]
Goal = Literal["FLUENCY", "BUSINESS", "EXAM", "TRAVEL"]
FocusArea = Literal["SPEAKING", "VOCABULARY", "WRITING"]
Topic = Literal[
    "DAILY_LIFE",
    "TRAVEL",
    "WORK",
    "EDUCATION",
    "TECHNOLOGY",
    "CULTURE",
    "HEALTH",
    "HOBBIES",
]
Comfort = Literal["BEGINNER", "SIMPLE", "COMFORTABLE", "CONFIDENT"]
AssessmentStatus = Literal[
    "IN_PROGRESS",
    "SUBMITTED",
    "PROCESSING",
    "COMPLETED",
    "FAILED_RETRYABLE",
    "FAILED_FINAL",
]


def unique_choices(values: list[str]) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError("Selections must not contain duplicates.")
    return values


def daily_minutes(value: int) -> int:
    if value not in (5, 10, 15, 20, 30, 45, 60):
        raise ValueError("Choose 5, 10, 15, 20, 30, 45, or 60 minutes.")
    return value


def timezone_name(value: str) -> str:
    value = value.strip()
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Use a valid IANA timezone, such as Asia/Riyadh.") from exc
    return value


Goals = Annotated[
    list[Goal], Field(min_length=1, max_length=4), AfterValidator(unique_choices)
]
FocusAreas = Annotated[
    list[FocusArea], Field(min_length=1, max_length=3), AfterValidator(unique_choices)
]
Topics = Annotated[list[Topic], Field(max_length=8), AfterValidator(unique_choices)]
DailyMinutes = Annotated[int, Field(strict=True), AfterValidator(daily_minutes)]
Timezone = Annotated[
    str, Field(min_length=1, max_length=80), AfterValidator(timezone_name)
]

# Shared with the profile PATCH so it cannot bypass validation of these keys.
PREFERENCE_ADAPTERS = {
    "goals": TypeAdapter(Goals),
    "focus_areas": TypeAdapter(FocusAreas),
    "daily_minutes": TypeAdapter(DailyMinutes),
    "topics": TypeAdapter(Topics),
    "self_reported_comfort": TypeAdapter(Comfort),
}


class LearningPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goals: Goals
    focus_areas: FocusAreas
    daily_minutes: DailyMinutes
    topics: Topics
    self_reported_comfort: Comfort


class SavePreferencesRequest(LearningPreferences):
    timezone: Timezone


class SavePreferencesResponse(BaseModel):
    status: OnboardingStatus
    saved: Literal[True] = True


class OnboardingState(BaseModel):
    status: OnboardingStatus
    next_step: Literal[
        "PREFERENCES",
        "ASSESSMENT",
        "ASSESSMENT_PROCESSING",
        "ASSESSMENT_RESULT",
        "ASSESSMENT_RETRY",
        "DASHBOARD",
    ]
    active_assessment_id: UUID | None = None
    assessment_status: AssessmentStatus | None = None
    can_access_dashboard: bool = False


class CompleteOnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_attempt_id: UUID


class CompleteOnboardingResponse(BaseModel):
    status: Literal["COMPLETED"] = "COMPLETED"
    learning_plan_id: UUID
    next_path: Literal["/dashboard"] = "/dashboard"
