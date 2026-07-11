import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func

from app.db.models.speaking import (
    SpeakingExercise,
    SpeakingSubmission,
    LiveConversationSession
)
from app.db.models.enums import (
    SpeakingExerciseType,
    SubmissionStatus,
    LiveSessionStatus
)
from app.schemas.speaking import (
    SpeakingSubmissionCreate,
    SpeakingSubmissionUpdate,
    LiveConversationSessionCreate
)


# ----------------------------------------
# Speaking Exercise CRUD
# ----------------------------------------
def get_exercise_by_day(
    db: Session, cycle: int, day: int, exercise_type: SpeakingExerciseType, target_cefr_level: str
) -> Optional[SpeakingExercise]:
    """
    Fetch the base exercise for a given cycle, day, and exercise type.
    """
    stmt = select(SpeakingExercise).where(
        and_(
            SpeakingExercise.cycle == cycle,
            SpeakingExercise.day == day,
            SpeakingExercise.type == exercise_type,
            SpeakingExercise.target_cefr_level == target_cefr_level
        )
    )
    return db.execute(stmt).scalars().first()

def get_exercise_by_id(db: Session, exercise_id: uuid.UUID) -> Optional[SpeakingExercise]:
    """
    Fetch a speaking exercise by its unique ID.
    """
    return db.query(SpeakingExercise).filter(SpeakingExercise.id == exercise_id).first()


# ----------------------------------------
# Speaking Submission CRUD
# ----------------------------------------
def create_submission(
    db: Session, user_id: uuid.UUID, obj_in: SpeakingSubmissionCreate
) -> SpeakingSubmission:
    """
    Create a new speaking submission record (Flow A).
    """
    db_obj = SpeakingSubmission(
        user_id=user_id,
        exercise_id=obj_in.exercise_id,
        audio_url=obj_in.audio_url,
        daily_activity_id=obj_in.daily_activity_id,
        status=SubmissionStatus.PENDING
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_submission(
    db: Session, submission_id: uuid.UUID
) -> Optional[SpeakingSubmission]:
    """
    Fetch a speaking submission by ID.
    """
    return db.get(SpeakingSubmission, submission_id)

def update_submission(
    db: Session, db_obj: SpeakingSubmission, obj_in: SpeakingSubmissionUpdate
) -> SpeakingSubmission:
    """
    Update a speaking submission (e.g., status, processing job ID, scores).
    """
    update_data = obj_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        # Handle dicts properly if they are coming as models
        if hasattr(value, "model_dump"):
            setattr(db_obj, field, value.model_dump())
        elif isinstance(value, list) and len(value) > 0 and hasattr(value[0], "model_dump"):
            setattr(db_obj, field, [item.model_dump() for item in value])
        else:
            setattr(db_obj, field, value)

    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_speaking_progress(db: Session, user_id: uuid.UUID) -> dict:
    """
    Aggregate the overall progress across both Flow A (Scripted) and Flow B (Live).
    Since both eventually map to SpeakingSubmission, we can aggregate directly from there.
    """
    stmt = (
        select(
            func.count(SpeakingSubmission.id).label("total_submissions"),
            func.avg(SpeakingSubmission.overall_score).label("avg_overall"),
            func.avg(SpeakingSubmission.fluency_score).label("avg_fluency"),
            func.avg(SpeakingSubmission.grammar_score).label("avg_grammar"),
            func.avg(SpeakingSubmission.vocabulary_score).label("avg_vocabulary")
        )
        .where(
            SpeakingSubmission.user_id == user_id,
            SpeakingSubmission.status == SubmissionStatus.COMPLETED
        )
    )
    result = db.execute(stmt).first()
    
    if not result or result.total_submissions == 0:
        return {
            "total_submissions": 0,
            "average_overall_score": 0.0,
            "average_fluency_score": 0.0,
            "average_grammar_score": 0.0,
            "average_vocabulary_score": 0.0,
        }
    
    return {
        "total_submissions": result.total_submissions,
        "average_overall_score": float(result.avg_overall or 0.0),
        "average_fluency_score": float(result.avg_fluency or 0.0),
        "average_grammar_score": float(result.avg_grammar or 0.0),
        "average_vocabulary_score": float(result.avg_vocabulary or 0.0),
    }

# ----------------------------------------
# Live Conversation Session CRUD
# ----------------------------------------
def create_live_session(
    db: Session, user_id: uuid.UUID, obj_in: LiveConversationSessionCreate
) -> LiveConversationSession:
    """
    Create a new live conversation session (Flow B).
    """
    db_obj = LiveConversationSession(
        user_id=user_id,
        topic=obj_in.topic,
        persona=obj_in.persona,
        target_duration_seconds=obj_in.target_duration_seconds,
        status=LiveSessionStatus.ACTIVE
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_live_session(
    db: Session, session_id: uuid.UUID
) -> Optional[LiveConversationSession]:
    """
    Fetch a live session by ID.
    """
    return db.get(LiveConversationSession, session_id)

def update_live_session(
    db: Session, db_obj: LiveConversationSession, update_data: Dict[str, Any]
) -> LiveConversationSession:
    """
    Update a live session (e.g., status, end details).
    """
    for field, value in update_data.items():
        if hasattr(value, "model_dump"):
            setattr(db_obj, field, value.model_dump())
        elif isinstance(value, list) and len(value) > 0 and hasattr(value[0], "model_dump"):
            setattr(db_obj, field, [item.model_dump() for item in value])
        else:
            setattr(db_obj, field, value)
            
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj
