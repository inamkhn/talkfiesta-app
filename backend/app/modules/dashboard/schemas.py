"""Explicit public dashboard projections."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assessment.schemas import Cefr
from app.modules.onboarding.schemas import FocusArea


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LearnerSummary(PublicModel):
    display_name: str | None
    timezone: str
    provisional_cefr: Cefr


class DashboardPlan(PublicModel):
    id: UUID
    cycle: int = Field(ge=1, le=5)
    daily_target_minutes: int = Field(gt=0, le=180)
    completed_required_activities: int = Field(ge=0, le=63)
    total_required_activities: int = Field(ge=21, le=63)
    overall_completion_percent: float = Field(ge=0, le=100)


class DashboardModule(PublicModel):
    module: FocusArea
    completed_days: int = Field(ge=0, le=21)
    total_days: Literal[21] = 21
    current_day: int = Field(ge=1, le=21)


class StreakSummary(PublicModel):
    current_days: int = Field(ge=0)
    longest_days: int = Field(ge=0)
    last_active_local_date: date | None


class PracticeSummary(PublicModel):
    total_seconds: int = Field(ge=0)
    today_seconds: int = Field(ge=0)
    mastered_words: int = Field(ge=0)


class TodayPreview(PublicModel):
    module: FocusArea
    day: int = Field(ge=1, le=21)
    title: str | None
    content_item_id: UUID | None


class PendingFeedback(PublicModel):
    submission_id: UUID
    module: FocusArea
    evaluation_status: Literal["PENDING", "PROCESSING"]
    submitted_at: datetime


class RecentAchievement(PublicModel):
    achievement_key: str
    earned_at: datetime


class DashboardResponse(PublicModel):
    learner: LearnerSummary
    learning_plan: DashboardPlan
    modules: list[DashboardModule] = Field(min_length=1, max_length=3)
    streak: StreakSummary
    practice: PracticeSummary
    today_preview: list[TodayPreview] = Field(min_length=1, max_length=3)
    pending_feedback: list[PendingFeedback] = Field(max_length=5)
    pending_feedback_count: int = Field(ge=0)
    recent_achievements: list[RecentAchievement] = Field(max_length=5)
