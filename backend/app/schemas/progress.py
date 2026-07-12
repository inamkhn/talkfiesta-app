from pydantic import BaseModel, ConfigDict
from datetime import date, datetime
from typing import List, Optional, Literal
from uuid import UUID

from app.db.models.enums import AchievementModule

class DailyProgressResponse(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    cycle: int
    day: int
    speaking_done: bool
    vocab_done: bool
    writing_done: bool
    total_practice_seconds: int

    model_config = ConfigDict(from_attributes=True)

class AchievementResponse(BaseModel):
    id: UUID
    key: str
    title: str
    description: str
    icon_url: Optional[str] = None
    module: Optional[AchievementModule] = None
    earned_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DashboardSummaryResponse(BaseModel):
    today_progress: DailyProgressResponse
    current_streak: int
    longest_streak: int
    total_xp: int  # Derived from total_practice_seconds or generic metric
    recent_achievements: List[AchievementResponse]

class TrackProgressRequest(BaseModel):
    module: Literal["speaking", "vocab", "writing"]
    practice_seconds: int = 0
