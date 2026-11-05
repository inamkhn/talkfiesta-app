"""Explicit public learning-plan projections."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.modules.assessment.schemas import Cefr
from app.modules.onboarding.schemas import FocusArea, FocusAreas, Goals

TimelineModule = Annotated[
    FocusArea,
    BeforeValidator(lambda value: value.upper() if isinstance(value, str) else value),
]


class PlanSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: UUID
    cycle: int = Field(ge=1, le=5)
    status: Literal["ACTIVE"]
    placement_cefr: Cefr
    placement_provisional: Literal[True] = True
    goals: Goals
    focus_areas: FocusAreas
    daily_target_minutes: int = Field(gt=0, le=180)
    created_at: datetime


class ModuleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    module: FocusArea
    progress_id: UUID
    status: Literal["ACTIVE", "AWAITING_CONTENT", "COMPLETED"]
    current_day: int = Field(ge=1, le=21)
    completed_days: int = Field(ge=0, le=21)
    total_days: Literal[21] = 21
    target_cefr: Cefr
    prioritized: bool

    @model_validator(mode="after")
    def completed_cycle(self):
        if self.status == "COMPLETED" and (
            self.current_day != 21 or self.completed_days != 21
        ):
            raise ValueError("Completed modules require 21 credited days.")
        return self


class CurrentPlanResponse(BaseModel):
    plan: PlanSummary
    modules: list[ModuleSummary] = Field(min_length=1, max_length=3)


class TodayActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    module: FocusArea
    day: int = Field(ge=1, le=21)
    content_item_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    content_kind: (
        Literal["SPEAKING_LESSON", "VOCABULARY_LESSON", "WRITING_LESSON"] | None
    ) = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    activity_status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED"]
    evaluation_status: None = None
    route: str | None = None


class TodayPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan_id: UUID
    cycle: int = Field(ge=1, le=5)
    daily_target_minutes: int = Field(gt=0, le=180)
    timezone: str
    activities: list[TodayActivity] = Field(min_length=1, max_length=3)


class TimelineDay(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    day: int = Field(ge=1, le=21)
    state: Literal["COMPLETED", "AVAILABLE", "LOCKED"]
    completed_at: datetime | None = None
    title: str | None = None


class ModuleTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    module: FocusArea
    progress_id: UUID
    cycle: int = Field(ge=1, le=5)
    current_day: int = Field(ge=1, le=21)
    status: Literal["ACTIVE", "AWAITING_CONTENT", "COMPLETED"]
    completed_days: int = Field(ge=0, le=21)
    total_days: Literal[21] = 21
    days: list[TimelineDay] = Field(min_length=21, max_length=21)
