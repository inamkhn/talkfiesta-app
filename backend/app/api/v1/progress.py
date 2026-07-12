from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Any
from datetime import date, timedelta
from uuid import UUID

from app.db.session import get_db
from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.models.progress import DailyProgress

from app.schemas.progress import (
    DailyProgressResponse,
    DashboardSummaryResponse,
    AchievementResponse,
    TrackProgressRequest
)
from app.crud.progress import (
    get_or_create_daily_progress,
    mark_module_completed,
    calculate_streak,
    get_user_achievements
)

router = APIRouter()

@router.get("/dashboard", response_model=DashboardSummaryResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get the unified dashboard progress for today.
    """
    today = date.today()
    today_progress = get_or_create_daily_progress(db, user_id=current_user.id, target_date=today)
    
    current_streak, longest_streak = calculate_streak(db, user_id=current_user.id)
    
    # Calculate Total XP over all time
    all_progress = db.query(DailyProgress).filter(DailyProgress.user_id == current_user.id).all()
    total_xp = sum(p.total_practice_seconds for p in all_progress) // 60  # 1 minute = 1 XP
    
    # Get recent achievements
    achievements = get_user_achievements(db, user_id=current_user.id)
    # Convert UserAchievement to AchievementResponse (mocked for now)
    achievement_responses = []
    for ua in achievements[:3]: # Get 3 most recent
        achievement_responses.append(
            AchievementResponse(
                id=ua.achievement.id,
                key=ua.achievement.key,
                title=ua.achievement.title,
                description=ua.achievement.description,
                icon_url=ua.achievement.icon_url,
                module=ua.achievement.module,
                earned_at=ua.earned_at
            )
        )
        
    return DashboardSummaryResponse(
        today_progress=today_progress,
        current_streak=current_streak,
        longest_streak=longest_streak,
        total_xp=total_xp,
        recent_achievements=achievement_responses
    )

@router.get("/history", response_model=List[DailyProgressResponse])
def get_progress_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get the last 30 days of progress for calendar heatmaps.
    """
    thirty_days_ago = date.today() - timedelta(days=30)
    
    history = db.query(DailyProgress).filter(
        DailyProgress.user_id == current_user.id,
        DailyProgress.date >= thirty_days_ago
    ).order_by(desc(DailyProgress.date)).all()
    
    return history

@router.get("/achievements", response_model=List[AchievementResponse])
def get_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get all earned achievements for the user.
    """
    achievements = get_user_achievements(db, user_id=current_user.id)
    return [
        AchievementResponse(
            id=ua.achievement.id,
            key=ua.achievement.key,
            title=ua.achievement.title,
            description=ua.achievement.description,
            icon_url=ua.achievement.icon_url,
            module=ua.achievement.module,
            earned_at=ua.earned_at
        ) for ua in achievements
    ]

@router.post("/track", response_model=DailyProgressResponse)
def track_progress(
    request: TrackProgressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Manually track progress or mark a module as completed for today.
    Note: Usually called by internal backend processes upon exercise submission.
    """
    today = date.today()
    progress = mark_module_completed(
        db, 
        user_id=current_user.id, 
        target_date=today, 
        module=request.module, 
        seconds=request.practice_seconds
    )
    
    return progress