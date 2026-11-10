"""Pydantic v2 response schemas for `/api/v1/progress` endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.progress.streaks import StreakStatus

ModuleLiteral = Literal["SPEAKING", "VOCABULARY", "WRITING"]
OverviewScope = Literal["current", "all"]


class ActivePlanOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    cycle: int = Field(ge=1, le=5)
    placement_cefr: str
    status: str
    required_modules: list[ModuleLiteral]
    required_activities: int = Field(ge=0)
    completed_activities: int = Field(ge=0)
    completion_percent: float = Field(ge=0.0, le=100.0)


class ModuleOverviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: ModuleLiteral
    status: str
    current_day: int = Field(ge=1, le=21)
    completed_days: int = Field(ge=0, le=21)
    total_days: int = 21
    completion_percent: float = Field(ge=0.0, le=100.0)


class PracticeOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_seconds: int = Field(ge=0)
    active_days: int = Field(ge=0)
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)


class VocabularyOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning: int = Field(ge=0)
    reviewing: int = Field(ge=0)
    mastered: int = Field(ge=0)
    due_now: int = Field(ge=0)


class AiFeedbackOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)


class ProgressOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    timezone: str
    active_plan: ActivePlanOverview | None
    modules: list[ModuleOverviewItem]
    practice: PracticeOverview
    vocabulary: VocabularyOverview
    ai_feedback: AiFeedbackOverview


class ModuleProgressBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    current_day: int = Field(ge=1, le=21)
    completed_days: int = Field(ge=0, le=21)
    total_days: int = 21
    completion_percent: float = Field(ge=0.0, le=100.0)


class SpeakingModuleMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_submissions: int = Field(ge=0)
    evaluated_submissions: int = Field(ge=0)
    pending_feedback: int = Field(ge=0)
    average_overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    average_words_per_minute: float | None = Field(default=None, ge=0.0)
    pronunciation_score: float | None = Field(default=None, ge=0.0, le=100.0)
    rubric_version: str | None = None
    comparability_warning: str | None = None


class WritingModuleMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_submissions: int = Field(ge=0)
    evaluated_submissions: int = Field(ge=0)
    pending_feedback: int = Field(ge=0)
    average_overall_score: float | None = Field(default=None, ge=0.0, le=100.0)
    average_word_count: float | None = Field(default=None, ge=0.0)
    total_revision_submissions: int = Field(ge=0)
    rubric_version: str | None = None
    comparability_warning: str | None = None


class VocabularyModuleMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unique_words_encountered: int = Field(ge=0)
    learning: int = Field(ge=0)
    reviewing: int = Field(ge=0)
    mastered: int = Field(ge=0)
    reviews_due: int = Field(ge=0)
    completed_daily_quizzes: int = Field(ge=0)
    average_quiz_score: float | None = Field(default=None, ge=0.0, le=100.0)


ModuleMetricsUnion = (
    SpeakingModuleMetrics | WritingModuleMetrics | VocabularyModuleMetrics
)


class RecentModuleSubmissionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    day: int | None = Field(default=None, ge=1, le=21)
    submitted_at: datetime | None = None
    evaluation_status: str
    score: float | None = Field(default=None, ge=0.0, le=100.0)


class ModuleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: ModuleLiteral
    cycle: int = Field(ge=1, le=5)
    progress: ModuleProgressBlock
    metrics: ModuleMetricsUnion
    recent_submissions: list[RecentModuleSubmissionItem] = Field(default_factory=list)


class StreakPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualifying_event: Literal[
        "AT_LEAST_ONE_VALID_ACTIVITY_COMPLETION_PER_LOCAL_DAY"
    ] = "AT_LEAST_ONE_VALID_ACTIVITY_COMPLETION_PER_LOCAL_DAY"
    today_required_to_keep_streak: bool = True
    grace_days: int = 0


class ProgressStreaksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str
    as_of_local_date: date
    current_streak_days: int = Field(ge=0)
    longest_streak_days: int = Field(ge=0)
    last_active_local_date: date | None = None
    active_days_total: int = Field(ge=0)
    streak_status: StreakStatus
    policy: StreakPolicy = Field(default_factory=StreakPolicy)


class ActivityCalendarDayItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    completion_count: int = Field(ge=1)
    modules: list[ModuleLiteral]
    practice_seconds: int = Field(ge=0)


class ActivityCalendarResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    timezone: str
    date_from: date = Field(alias="from", serialization_alias="from")
    date_to: date = Field(alias="to", serialization_alias="to")
    module: ModuleLiteral | None = None
    active_days: int = Field(ge=0)
    total_completions: int = Field(ge=0)
    total_seconds: int = Field(ge=0)
    days: list[ActivityCalendarDayItem] = Field(default_factory=list)


AchievementFilterStatus = Literal["all", "earned", "locked"]
AchievementBadgeStatus = Literal["EARNED", "LOCKED"]


class AchievementProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current: int = Field(ge=0)
    target: int = Field(ge=1)


class AchievementItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    description: str
    status: AchievementBadgeStatus
    earned_at: datetime | None = None
    progress: AchievementProgress


class AchievementsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    earned_count: int = Field(ge=0)
    available_count: int = Field(ge=0)
    achievements: list[AchievementItem] = Field(default_factory=list)


TrendGranularity = Literal["day", "week"]


class TrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: date
    value: float
    sample_size: int = Field(ge=1)


class ModuleTrendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: ModuleLiteral
    metric: str
    granularity: TrendGranularity
    rubric_version: str | None = None
    aggregation: str
    unit: str
    points: list[TrendPoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ActivityHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completion_id: UUID
    module: ModuleLiteral
    cycle: int = Field(ge=1, le=5)
    day: int | None = Field(default=None, ge=1, le=21)
    title: str
    completed_at: datetime
    local_practice_date: date
    practice_seconds: int = Field(ge=0)
    source_submission_id: UUID | None = None
    evaluation_status: str | None = None
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    details_url: str | None = None


class ActivityHistoryPagination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_cursor: str | None = None
    has_more: bool = False


class ActivityHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ActivityHistoryItem] = Field(default_factory=list)
    pagination: ActivityHistoryPagination


AssessmentKindLiteral = Literal["INITIAL", "REASSESSMENT"]


class CefrAssessmentHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: UUID
    kind: AssessmentKindLiteral
    completed_at: datetime
    placement_cefr: str
    confidence: str | None = None
    rubric_version: str


class CefrHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_placement_cefr: str | None = None
    certified: Literal[False] = False
    assessments: list[CefrAssessmentHistoryItem] = Field(default_factory=list)








