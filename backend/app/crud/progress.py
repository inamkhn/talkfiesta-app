import uuid
from datetime import date, timedelta
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.models.progress import DailyProgress, Achievement, UserAchievement

def get_or_create_daily_progress(db: Session, user_id: uuid.UUID, target_date: date) -> DailyProgress:
    """
    Fetches the DailyProgress for a given date.
    If it doesn't exist, creates it while calculating the correct cycle and day.
    """
    progress = db.query(DailyProgress).filter(
        DailyProgress.user_id == user_id,
        DailyProgress.date == target_date
    ).first()

    if progress:
        return progress

    # Determine cycle and day based on the most recent progress
    last_progress = db.query(DailyProgress).filter(
        DailyProgress.user_id == user_id,
        DailyProgress.date < target_date
    ).order_by(desc(DailyProgress.date)).first()

    if not last_progress:
        # First day ever!
        cycle = 1
        day = 1
    else:
        # Check if they completed the previous day's curriculum (for strict progression)
        # For simplicity in this app, we advance the day index whenever they practice on a new day.
        # Wait, if they missed a day, does the day index still advance?
        # Yes, we'll advance it by 1 from their last active day.
        if last_progress.day >= 21:
            cycle = last_progress.cycle + 1
            day = 1
        else:
            cycle = last_progress.cycle
            day = last_progress.day + 1

    new_progress = DailyProgress(
        user_id=user_id,
        date=target_date,
        cycle=cycle,
        day=day
    )
    db.add(new_progress)
    db.commit()
    db.refresh(new_progress)
    return new_progress

def mark_module_completed(db: Session, user_id: uuid.UUID, target_date: date, module: str, seconds: int = 0) -> DailyProgress:
    """
    Marks a specific module (speaking, writing, vocab) as done for the day and adds practice time.
    """
    progress = get_or_create_daily_progress(db, user_id, target_date)
    
    if module == 'speaking':
        progress.speaking_done = True
    elif module == 'writing':
        progress.writing_done = True
    elif module == 'vocab':
        progress.vocab_done = True
        
    progress.total_practice_seconds += seconds
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress

def calculate_streak(db: Session, user_id: uuid.UUID) -> Tuple[int, int]:
    """
    Calculates the current streak and longest streak.
    A streak day is defined as any day with at least one module completed.
    """
    all_progress = db.query(DailyProgress).filter(
        DailyProgress.user_id == user_id,
        (DailyProgress.speaking_done == True) | 
        (DailyProgress.writing_done == True) | 
        (DailyProgress.vocab_done == True)
    ).order_by(desc(DailyProgress.date)).all()
    
    if not all_progress:
        return 0, 0
        
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    last_date = None
    
    # Iterate backwards through history
    for p in all_progress:
        if last_date is None:
            temp_streak = 1
            # Check if current streak is still active (today or yesterday)
            if p.date >= date.today() - timedelta(days=1):
                current_streak = 1
        else:
            diff = (last_date - p.date).days
            if diff == 1:
                temp_streak += 1
                if current_streak > 0 and current_streak == temp_streak - 1:
                    current_streak = temp_streak
            elif diff > 1:
                temp_streak = 1
                
        if temp_streak > longest_streak:
            longest_streak = temp_streak
            
        last_date = p.date
        
    return current_streak, longest_streak

def get_user_achievements(db: Session, user_id: uuid.UUID):
    """
    Fetches all achievements unlocked by the user, newest first.
    """
    return db.query(UserAchievement).filter(
        UserAchievement.user_id == user_id
    ).order_by(desc(UserAchievement.earned_at)).all()
