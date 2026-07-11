from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Any

from app.db.session import get_db
from app.schemas.speaking import (
    SpeakingExerciseResponse,
    SpeakingSubmissionCreate,
    SpeakingSubmissionResponse,
    SpeakingProgressResponse
)
from app.crud.speaking import (
    get_exercise_by_day,
    get_exercise_by_id,
    create_submission,
    get_submission,
    get_speaking_progress
)
from app.db.models.enums import SpeakingExerciseType
from app.workers.speaking_tasks import process_speaking_submission
from app.api.deps import get_current_user
from app.db.models.user import User

router = APIRouter()

@router.get("/exercise/{cycle}/{day}", response_model=SpeakingExerciseResponse)
def fetch_exercise(
    cycle: int,
    day: int,
    exercise_type: SpeakingExerciseType = SpeakingExerciseType.CONVERSATIONAL,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Fetch the scripted exercise for a given cycle, day, and type.
    """
    target_cefr_level = current_user.cefr_level or "B1"
    exercise = get_exercise_by_day(db, cycle=cycle, day=day, exercise_type=exercise_type, target_cefr_level=target_cefr_level)
    if not exercise:
        raise HTTPException(status_code=404, detail="Speaking exercise not found")
    return exercise

@router.post("/submit", response_model=SpeakingSubmissionResponse)
def submit_audio(
    submission_in: SpeakingSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Upload recorded audio reference and trigger async evaluation (Flow A).
    """
    exercise = get_exercise_by_id(db, exercise_id=submission_in.exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Speaking exercise not found")
        
    submission = create_submission(db, user_id=current_user.id, obj_in=submission_in)
    
    # Enqueue celery job
    task = process_speaking_submission.delay(str(submission.id))
    submission.processing_job_id = task.id
    db.commit()
    
    return submission

@router.get("/session/{submission_id}", response_model=SpeakingSubmissionResponse)
def get_submission_status(
    submission_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Poll the status and results of a speaking submission.
    """
    submission = get_submission(db, submission_id=submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this submission")
    
    return submission

@router.get("/progress", response_model=SpeakingProgressResponse)
def get_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get aggregated speaking progress metrics for the user.
    """
    return get_speaking_progress(db, user_id=current_user.id)
