import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.models.vocabulary import (
    VocabularyWord,
    VocabularyExerciseBank,
    UserVocabulary,
    VocabularyPracticeSession,
    PersonalizedVocabSuggestion,
)
from app.db.models.enums import VocabWordStatus, SuggestionStatus
from app.schemas.vocabulary import SessionCompleteRequest


def get_day_words(db: Session, cycle: int, day: int, target_cefr_level: str) -> List[VocabularyWord]:
    """
    Retrieve all VocabularyWord entries configured for a specific cycle, day,
    and CEFR level along with their deterministic pre-generated exercises.
    """
    return (
        db.query(VocabularyWord)
        .filter(
            VocabularyWord.cycle == cycle, 
            VocabularyWord.day == day,
            VocabularyWord.target_cefr_level == target_cefr_level
        )
        .options(joinedload(VocabularyWord.exercises))
        .all()
    )


def get_word_by_id(db: Session, word_id: uuid.UUID) -> Optional[VocabularyWord]:
    """
    Retrieve a specific VocabularyWord by its UUID.
    """
    return (
        db.query(VocabularyWord)
        .filter(VocabularyWord.id == word_id)
        .options(joinedload(VocabularyWord.exercises))
        .first()
    )


def get_exercise_bank_by_word_id(db: Session, word_id: uuid.UUID) -> Optional[VocabularyExerciseBank]:
    """
    Fetch the pre-generated exercise configuration for a vocabulary word.
    """
    return db.query(VocabularyExerciseBank).filter(VocabularyExerciseBank.word_id == word_id).first()


def get_user_vocab_entry(db: Session, user_id: uuid.UUID, word_id: uuid.UUID) -> Optional[UserVocabulary]:
    """
    Lookup a user's spaced-repetition record for a specific word.
    """
    return db.query(UserVocabulary).filter(
        UserVocabulary.user_id == user_id,
        UserVocabulary.word_id == word_id
    ).first()


def get_or_create_user_vocabulary(
    db: Session, user_id: uuid.UUID, word_id: uuid.UUID, day_number: int
) -> UserVocabulary:
    """
    Get the user's vocabulary progress record, or initialize a new one (learned).
    """
    uv = get_user_vocab_entry(db, user_id, word_id)
    if not uv:
        # First time learning the word, schedule the first review tomorrow (Day N + 1)
        next_review = datetime.now(timezone.utc) + timedelta(days=1)
        uv = UserVocabulary(
            user_id=user_id,
            word_id=word_id,
            day_number=day_number,
            mastery_level=1,
            status=VocabWordStatus.LEARNING,
            times_practiced=0,
            times_reviewed=0,
            interval_days=1,
            next_review_date=next_review,
            learned_at=datetime.now(timezone.utc),
        )
        db.add(uv)
        db.commit()
        db.refresh(uv)
    return uv


def update_user_vocabulary_mastery(
    db: Session, user_vocab_id: uuid.UUID, is_correct: bool
) -> UserVocabulary:
    """
    Applies the spaced repetition scheduling logic when a review exercise is completed.
    Intervals: [1, 2, 4, 7, 14] days.
    """
    uv = db.query(UserVocabulary).filter(UserVocabulary.id == user_vocab_id).first()
    if not uv:
        raise ValueError("User vocabulary record not found")
        
    intervals = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
    
    uv.times_reviewed += 1
    uv.last_reviewed_at = datetime.now(timezone.utc)
    
    if is_correct:
        uv.mastery_level = min(5, uv.mastery_level + 1)
        if uv.mastery_level == 5:
            uv.status = VocabWordStatus.MASTERED
            uv.mastered_at = datetime.now(timezone.utc)
        elif uv.mastery_level >= 3:
            uv.status = VocabWordStatus.REVIEWING
    else:
        # Drop mastery level significantly, schedule retry tomorrow
        uv.mastery_level = max(1, uv.mastery_level - 2)
        uv.status = VocabWordStatus.LEARNING
        uv.mastered_at = None  # Reset mastery timestamp if user forgot it
        
    # Calculate next review date based on the new level
    uv.interval_days = intervals.get(uv.mastery_level, 1)
    uv.next_review_date = datetime.now(timezone.utc) + timedelta(days=uv.interval_days)
    
    db.add(uv)
    db.commit()
    db.refresh(uv)
    return uv


def increment_word_practice_count(db: Session, user_id: uuid.UUID, word_id: uuid.UUID) -> UserVocabulary:
    """
    Increment practice counters for words practiced in active daily sessions.
    """
    uv = get_user_vocab_entry(db, user_id, word_id)
    if uv:
        uv.times_practiced += 1
        db.add(uv)
        db.commit()
        db.refresh(uv)
    return uv


def get_review_queue(db: Session, user_id: uuid.UUID, limit: int = 10) -> List[UserVocabulary]:
    """
    Get the list of vocabulary words currently due for spaced-repetition reviews.
    Prioritizes lower mastery levels first, then the most overdue.
    """
    now = datetime.now(timezone.utc)
    return (
        db.query(UserVocabulary)
        .filter(
            UserVocabulary.user_id == user_id,
            UserVocabulary.next_review_date <= now,
            UserVocabulary.status != VocabWordStatus.MASTERED,  # Mastered words don't show up in daily review queue
        )
        .options(joinedload(UserVocabulary.word).joinedload(VocabularyWord.exercises))
        .order_by(UserVocabulary.mastery_level.asc(), UserVocabulary.next_review_date.asc())
        .limit(limit)
        .all()
    )


def create_practice_session(
    db: Session, user_id: uuid.UUID, session_data: SessionCompleteRequest, overall_score: int
) -> VocabularyPracticeSession:
    """
    Log a completed daily vocabulary practice session score record.
    """
    session = VocabularyPracticeSession(
        user_id=user_id,
        daily_activity_id=session_data.daily_activity_id,
        day_number=session_data.day_number,
        fill_blank_score=session_data.fill_blank_score,
        match_score=session_data.match_score,
        context_score=session_data.context_score,
        pronunciation_score=session_data.pronunciation_score,
        overall_score=overall_score,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_personal_suggestions(
    db: Session, user_id: uuid.UUID, status: SuggestionStatus = SuggestionStatus.PENDING
) -> List[PersonalizedVocabSuggestion]:
    """
    Fetch personalized AI-generated vocabulary alternative suggestions for a user.
    """
    return (
        db.query(PersonalizedVocabSuggestion)
        .filter(
            PersonalizedVocabSuggestion.user_id == user_id,
            PersonalizedVocabSuggestion.status == status
        )
        .order_by(PersonalizedVocabSuggestion.created_at.desc())
        .all()
    )


def update_suggestion_status(
    db: Session, suggestion_id: uuid.UUID, new_status: SuggestionStatus
) -> Optional[PersonalizedVocabSuggestion]:
    """
    Update status of a personalized suggestion (e.g., ADDED_TO_QUEUE, DISMISSED).
    """
    suggestion = db.query(PersonalizedVocabSuggestion).filter(PersonalizedVocabSuggestion.id == suggestion_id).first()
    if suggestion:
        suggestion.status = new_status
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
    return suggestion


def get_user_vocab_bank(
    db: Session,
    user_id: uuid.UUID,
    page: int = 1,
    per_page: int = 10,
    search: Optional[str] = None,
    status: Optional[VocabWordStatus] = None,
) -> Tuple[int, List[UserVocabulary]]:
    """
    Fetch a paginated view of all words the user has started learning.
    Allows searching by word name and filtering by mastery status.
    """
    query = (
        db.query(UserVocabulary)
        .join(VocabularyWord)
        .filter(UserVocabulary.user_id == user_id)
        .options(joinedload(UserVocabulary.word))
    )
    
    if search:
        query = query.filter(VocabularyWord.word.ilike(f"%{search.strip()}%"))
        
    if status:
        query = query.filter(UserVocabulary.status == status)
        
    total_count = query.count()
    
    offset = (page - 1) * per_page
    items = (
        query.order_by(VocabularyWord.word.asc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    
    return total_count, items


def get_user_vocab_stats(db: Session, user_id: uuid.UUID) -> dict:
    """
    Compute aggregate statistics on vocabulary metrics for a user's dashboard.
    """
    # Total learned
    total_learned = db.query(UserVocabulary).filter(UserVocabulary.user_id == user_id).count()
    
    # Mastered count
    mastered_count = db.query(UserVocabulary).filter(
        UserVocabulary.user_id == user_id,
        UserVocabulary.status == VocabWordStatus.MASTERED
    ).count()
    
    # Learning count
    learning_count = db.query(UserVocabulary).filter(
        UserVocabulary.user_id == user_id,
        UserVocabulary.status == VocabWordStatus.LEARNING
    ).count()
    
    # Reviewing count
    reviewing_count = db.query(UserVocabulary).filter(
        UserVocabulary.user_id == user_id,
        UserVocabulary.status == VocabWordStatus.REVIEWING
    ).count()
    
    # Review due count
    now = datetime.now(timezone.utc)
    review_due_count = db.query(UserVocabulary).filter(
        UserVocabulary.user_id == user_id,
        UserVocabulary.next_review_date <= now,
        UserVocabulary.status != VocabWordStatus.MASTERED
    ).count()
    
    return {
        "total_learned": total_learned,
        "mastered_count": mastered_count,
        "learning_count": learning_count,
        "reviewing_count": reviewing_count,
        "review_due_count": review_due_count,
    }
