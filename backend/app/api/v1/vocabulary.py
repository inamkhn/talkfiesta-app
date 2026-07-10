import uuid
from typing import Any, List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import vocabulary as crud_vocab
from app.crud import user as crud_user
from app.db.models.user import User
from app.db.models.enums import VocabWordStatus, SuggestionStatus
from app.services import gemini_client, deepgram_client
import difflib
import string
from app.middleware.rate_limit import check_ai_rate_limit
from app.schemas.vocabulary import (
    DayWordsResponse,
    WordWithExerciseResponse,
    WordCardResponse,
    ExerciseBankResponse,
    FillBlankSubmission,
    FillBlankResult,
    MatchSubmission,
    MatchResult,
    MatchPairResult,
    ContextSubmission,
    ContextResult,
    ContextPairResult,
    PronunciationSubmission,
    PronunciationResult,
    SessionCompleteRequest,
    SessionCompleteResponse,
    WordMasteryUpdate,
    ReviewQueueResponse,
    ReviewQueueWord,
    ReviewSubmission,
    ReviewSubmissionResult,
    PersonalSuggestionResponse,
    VocabBankResponse,
    UserVocabBankWord,
    VocabStatsResponse,
)

router = APIRouter()


@router.get("/day/{day}", response_model=DayWordsResponse)
def get_daily_vocabulary(
    day: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve today's list of 10 vocabulary words plus pre-generated exercises.
    """
    profile = crud_user.get_learning_profile(db, user_id=current_user.id)
    cycle = profile.current_cycle if profile else 1
    cefr_level = profile.target_cefr_level if profile else "A1"
    
    words = crud_vocab.get_day_words(db, cycle=cycle, day=day, target_cefr_level=cefr_level)
    if not words:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No vocabulary words configured for cycle {cycle}, day {day}, level {cefr_level}",
        )
        
    response_words = []
    for word in words:
        # Get the first exercise configuration for this word
        exercise = word.exercises[0] if word.exercises else None
        if not exercise:
            # Fallback placeholder if no exercise was configured in the DB
            exercise = crud_vocab.VocabularyExerciseBank(
                id=uuid.uuid4(),
                word_id=word.id,
                fill_blank_sentence=f"Placeholder sentence using the word [blank].",
                fill_blank_correct_answer=word.word,
                match_definition_distractor_1="Wrong distractor 1",
                match_definition_distractor_2="Wrong distractor 2",
                match_definition_distractor_3="Wrong distractor 3",
            )
        response_words.append(
            WordWithExerciseResponse(
                word=WordCardResponse.model_validate(word),
                exercise=ExerciseBankResponse.model_validate(exercise),
            )
        )
        
    return DayWordsResponse(cycle=cycle, day=day, words=response_words)


@router.post("/exercise/fill-blank/submit", response_model=FillBlankResult)
def submit_fill_blank(
    submission: FillBlankSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Deterministic grading for the fill-in-the-blank exercise. (No LLM call)
    """
    exercise = crud_vocab.get_exercise_bank_by_word_id(db, word_id=submission.word_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise bank not found for the target word ID",
        )
        
    is_correct = (
        submission.user_answer.strip().lower()
        == exercise.fill_blank_correct_answer.strip().lower()
    )
    
    return FillBlankResult(
        word_id=submission.word_id,
        is_correct=is_correct,
        correct_answer=exercise.fill_blank_correct_answer,
    )


@router.post("/exercise/match/submit", response_model=MatchResult)
def submit_match(
    submission: MatchSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Deterministic grading for definition matching exercise. (No LLM call)
    """
    results = []
    correct_count = 0
    
    for pair in submission.pairs:
        word = crud_vocab.get_word_by_id(db, word_id=pair.word_id)
        if not word:
            continue
            
        is_correct = pair.selected_definition.strip() == word.definition.strip()
        if is_correct:
            correct_count += 1
            
        results.append(
            MatchPairResult(
                word_id=pair.word_id,
                is_correct=is_correct,
                correct_definition=word.definition,
            )
        )
        
    return MatchResult(pairs=results, score=correct_count)


@router.post("/exercise/context/submit", response_model=ContextResult)
def submit_context(
    submission: ContextSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    _rate_limit: None = Depends(check_ai_rate_limit),
) -> Any:
    """
    Grading for 'Use in Context' sentences. Evaluates all 5 sentences together using 1 batched Gemini call.
    """
    pairs_for_ai = []
    word_map = {}
    
    for pair in submission.submissions:
        word = crud_vocab.get_word_by_id(db, word_id=pair.word_id)
        if not word:
            continue
            
        word_map[str(pair.word_id)] = word
        pairs_for_ai.append(
            {
                "word_id": str(pair.word_id),
                "word": word.word,
                "definition": word.definition,
                "sentence": pair.sentence,
            }
        )
        
    if not pairs_for_ai:
        return ContextResult(results=[], score=0)
        
    # Call batched Gemini grading service
    ai_response = gemini_client.grade_context_sentences(pairs_for_ai)
    
    results = []
    correct_count = 0
    
    for result in ai_response.get("results", []):
        is_correct = result.get("is_correct", False)
        if is_correct:
            correct_count += 1
            
        results.append(
            ContextPairResult(
                word_id=uuid.UUID(result["word_id"]),
                is_correct=is_correct,
                feedback=result["feedback"],
            )
        )
        
    return ContextResult(results=results, score=correct_count)


@router.post("/exercise/pronunciation/submit", response_model=PronunciationResult)
def submit_pronunciation(
    submission: PronunciationSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    _rate_limit: None = Depends(check_ai_rate_limit),
) -> Any:
    """
    Grade user pronunciation using Deepgram STT and string matching.
    """
    word = crud_vocab.get_word_by_id(db, word_id=submission.word_id)
    if not word:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Word not found",
        )
        
    # Transcribe the audio
    transcript = deepgram_client.transcribe_audio(
        submission.audio_url, target_word=word.word
    )
    
    # Normalize strings for comparison
    normalized_target = word.word.lower().strip().translate(str.maketrans("", "", string.punctuation))
    normalized_transcript = transcript.lower().strip().translate(str.maketrans("", "", string.punctuation))
    
    # Calculate similarity ratio
    if not normalized_transcript:
        score = 0
    elif normalized_target in normalized_transcript:
        # If the target word is explicitly heard in the transcript, give full credit
        score = 100
    else:
        matcher = difflib.SequenceMatcher(None, normalized_target, normalized_transcript)
        score = int(matcher.ratio() * 100)
        
    # Generate helpful tips
    if score >= 90:
        tip = "Great pronunciation! Intonation matches correctly."
    elif score >= 70:
        tip = f"Pronunciation is close, but we transcribed '{transcript}'. Try to emphasize each syllable clearly."
    else:
        tip = f"Hmm, that sounded like '{transcript}'. Try breaking the word down phonetically and repeating it slowly."
        
    return PronunciationResult(
        word_id=submission.word_id,
        score=score,
        tip=tip,
    )


@router.post("/session/complete", response_model=SessionCompleteResponse)
def complete_practice_session(
    session_data: SessionCompleteRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Finalize daily practice scores, register newly learned words in user review records, and log the practice stats.
    """
    # Calculate overall weighted score out of 100
    # Formula: (fill_blank + match + context) * 20 / 3 + pronunciation_score * 0.4
    exercise_score = (session_data.fill_blank_score + session_data.match_score + session_data.context_score) * 20 / 3
    overall = int((exercise_score * 0.6) + (session_data.pronunciation_score * 0.4))
    overall_score = max(0, min(100, overall))
    
    # Log practice session in DB
    session = crud_vocab.create_practice_session(
        db, user_id=current_user.id, session_data=session_data, overall_score=overall_score
    )
    
    # Eagerly initialize user's newly-learned words into the spaced repetition queue
    profile = crud_user.get_learning_profile(db, user_id=current_user.id)
    cycle = profile.current_cycle if profile else 1
    words = crud_vocab.get_day_words(db, cycle=cycle, day=session_data.day_number)
    
    mastery_updates = []
    for word in words:
        # Practice increments counts
        uv = crud_vocab.get_or_create_user_vocabulary(
            db, user_id=current_user.id, word_id=word.id, day_number=session_data.day_number
        )
        crud_vocab.increment_word_practice_count(db, user_id=current_user.id, word_id=word.id)
        
        mastery_updates.append(
            WordMasteryUpdate(
                word_id=word.id,
                word=word.word,
                previous_level=uv.mastery_level,
                new_level=uv.mastery_level,
                next_review_date=uv.next_review_date,
            )
        )
        
    return SessionCompleteResponse(
        session_id=session.id,
        overall_score=overall_score,
        completed_at=session.completed_at,
        mastery_updates=mastery_updates,
    )


@router.get("/review/today", response_model=ReviewQueueResponse)
def get_today_reviews(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve old words currently due for spaced-repetition review.
    """
    due_items = crud_vocab.get_review_queue(db, user_id=current_user.id, limit=limit)
    
    words_response = []
    for uv in due_items:
        exercise = uv.word.exercises[0] if uv.word.exercises else None
        if not exercise:
            exercise = crud_vocab.VocabularyExerciseBank(
                id=uuid.uuid4(),
                word_id=uv.word_id,
                fill_blank_sentence=f"Placeholder review sentence for [blank].",
                fill_blank_correct_answer=uv.word.word,
                match_definition_distractor_1="Wrong distractor 1",
                match_definition_distractor_2="Wrong distractor 2",
                match_definition_distractor_3="Wrong distractor 3",
            )
            
        words_response.append(
            ReviewQueueWord(
                user_vocab_id=uv.id,
                word=WordCardResponse.model_validate(uv.word),
                exercise=ExerciseBankResponse.model_validate(exercise),
                mastery_level=uv.mastery_level,
                status=uv.status,
                next_review_date=uv.next_review_date,
            )
        )
        
    return ReviewQueueResponse(due_count=len(words_response), words=words_response)


@router.post("/review/submit", response_model=ReviewSubmissionResult)
def submit_review_session(
    submission: ReviewSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Process spaced-repetition grades, adapting intervals and mastery levels.
    """
    updated_words = []
    
    for item in submission.reviews:
        try:
            previous_uv = db.query(crud_vocab.UserVocabulary).filter(crud_vocab.UserVocabulary.id == item.user_vocab_id).first()
            prev_level = previous_uv.mastery_level if previous_uv else 1
            
            uv = crud_vocab.update_user_vocabulary_mastery(
                db, user_vocab_id=item.user_vocab_id, is_correct=item.is_correct
            )
            
            updated_words.append(
                WordMasteryUpdate(
                    word_id=uv.word_id,
                    word=uv.word.word,
                    previous_level=prev_level,
                    new_level=uv.mastery_level,
                    next_review_date=uv.next_review_date,
                )
            )
        except Exception:
            continue
            
    return ReviewSubmissionResult(updated_words=updated_words)


@router.get("/personal-suggestions", response_model=List[PersonalSuggestionResponse])
def get_personalized_suggestions(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve pending custom suggestions generated asynchronously from user transcripts.
    """
    suggestions = crud_vocab.get_personal_suggestions(db, user_id=current_user.id)
    return suggestions


@router.put("/personal-suggestions/{id}", response_model=PersonalSuggestionResponse)
def update_suggestion(
    id: uuid.UUID,
    status_update: SuggestionStatus = Query(..., description="Target status"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a suggestions status (dismiss or accept it).
    """
    suggestion = crud_vocab.update_suggestion_status(db, suggestion_id=id, new_status=status_update)
    if not suggestion or suggestion.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )
    return suggestion


@router.get("/bank", response_model=VocabBankResponse)
def get_vocabulary_bank(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status_filter: Optional[VocabWordStatus] = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Fetch a paginated personal list of all words learned, with mastery states.
    """
    total, items = crud_vocab.get_user_vocab_bank(
        db,
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        search=search,
        status=status_filter,
    )
    
    words_data = []
    for uv in items:
        words_data.append(
            UserVocabBankWord(
                id=uv.word.id,
                word=uv.word.word,
                definition=uv.word.definition,
                part_of_speech=uv.word.part_of_speech,
                category=uv.word.category,
                target_cefr_level=uv.word.target_cefr_level,
                mastery_level=uv.mastery_level,
                status=uv.status,
                times_practiced=uv.times_practiced,
                times_reviewed=uv.times_reviewed,
                next_review_date=uv.next_review_date,
                learned_at=uv.learned_at,
                mastered_at=uv.mastered_at,
            )
        )
        
    pages_count = (total + per_page - 1) // per_page
    return VocabBankResponse(
        total_count=total,
        page=page,
        per_page=per_page,
        pages_count=pages_count,
        words=words_data,
    )


@router.get("/stats", response_model=VocabStatsResponse)
def get_vocab_statistics(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get user vocabulary progress metrics for dashboard display.
    """
    stats = crud_vocab.get_user_vocab_stats(db, user_id=current_user.id)
    return VocabStatsResponse(
        total_learned=stats["total_learned"],
        mastered_count=stats["mastered_count"],
        learning_count=stats["learning_count"],
        reviewing_count=stats["reviewing_count"],
        review_due_count=stats["review_due_count"],
    )
