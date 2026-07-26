import logging
import uuid
from typing import Any, List, Dict, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.crud import vocabulary as crud_vocab
from app.crud import user as crud_user
from app.db.models.user import User
from app.db.models.enums import VocabWordStatus, SuggestionStatus
from app.services import gemini_client, deepgram_client
from app.services.deepgram_client import DeepgramAPIError
import difflib
import string
from app.middleware.rate_limit import check_ai_rate_limit, refund_ai_rate_limit
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
    ReviewWordFailure,
    PersonalSuggestionResponse,
    VocabBankResponse,
    UserVocabBankWord,
    VocabStatsResponse,
)

logger = logging.getLogger("app.api.v1.vocabulary")

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
    
    word_ids = [pair.word_id for pair in submission.pairs]
    words = db.query(crud_vocab.VocabularyWord).filter(crud_vocab.VocabularyWord.id.in_(word_ids)).all()
    word_dict = {w.id: w for w in words}
    
    for pair in submission.pairs:
        word = word_dict.get(pair.word_id)
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
) -> Any:
    """
    Grading for 'Use in Context' sentences. Evaluates all 5 sentences together using 1 batched Gemini call.
    """
    pairs_for_ai = []
    word_map = {}
    
    word_ids = [pair.word_id for pair in submission.submissions]
    words = db.query(crud_vocab.VocabularyWord).filter(crud_vocab.VocabularyWord.id.in_(word_ids)).all()
    word_dict = {w.id: w for w in words}
    
    for pair in submission.submissions:
        word = word_dict.get(pair.word_id)
        if not word or str(pair.word_id) in word_map:
            # Skip unknown word IDs and duplicate submissions for the same word
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
        
    # Consume AI quota only once validation confirms a Gemini call will actually happen
    check_ai_rate_limit(current_user)
    
    # Call batched Gemini grading service
    ai_response = gemini_client.grade_context_sentences(pairs_for_ai)
    degraded = bool(ai_response.get("degraded", False))
    if degraded:
        # Nothing was actually graded; give the quota back
        refund_ai_rate_limit(str(current_user.id))
    
    results = []
    correct_count = 0
    graded_ids = set()
    
    for result in ai_response.get("results", []):
        if not isinstance(result, dict):
            continue
        raw_id = result.get("word_id")
        # Only trust results that map back to a word we actually submitted
        if not isinstance(raw_id, str) or raw_id not in word_map or raw_id in graded_ids:
            continue
        graded_ids.add(raw_id)
        
        is_correct = bool(result.get("is_correct", False))
        if is_correct:
            correct_count += 1
            
        results.append(
            ContextPairResult(
                word_id=uuid.UUID(raw_id),
                is_correct=is_correct,
                feedback=str(result.get("feedback", "")),
            )
        )
        
    # Any submitted pair the AI failed to return a grade for gets an explicit notice
    for word_id_str in word_map:
        if word_id_str not in graded_ids:
            results.append(
                ContextPairResult(
                    word_id=uuid.UUID(word_id_str),
                    is_correct=False,
                    feedback="We couldn't grade this sentence this time. Please submit it again.",
                )
            )
            
    return ContextResult(results=results, score=correct_count, degraded=degraded)


@router.post("/exercise/pronunciation/submit", response_model=PronunciationResult)
def submit_pronunciation(
    submission: PronunciationSubmission,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Grade user pronunciation using Deepgram STT and string matching.
    """
    # Basic sanity validation of the client-supplied URL before handing it to Deepgram
    parsed = urlparse(submission.audio_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="audio_url must be a valid http(s) URL",
        )
        
    word = crud_vocab.get_word_by_id(db, word_id=submission.word_id)
    if not word:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Word not found",
        )
        
    # Deepgram is a metered API: consume AI quota only after validations pass
    check_ai_rate_limit(current_user)
    
    # Transcribe the audio. Simulation is only used when no API key is configured
    # (dev mode); a real Deepgram failure must not silently award a fake score.
    degraded = not settings.DEEPGRAM_API_KEY
    try:
        transcript = deepgram_client.transcribe_audio(
            submission.audio_url, target_word=word.word, raise_on_failure=True
        )
    except DeepgramAPIError:
        refund_ai_rate_limit(str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pronunciation scoring is temporarily unavailable. Please try again later.",
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
        degraded=degraded,
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
    # Idempotency guard: a duplicate POST (retry/double-click) within 60s returns
    # the already-recorded session instead of double-counting practice stats.
    recent = crud_vocab.get_recent_practice_session(
        db, user_id=current_user.id, day_number=session_data.day_number
    )
    if recent:
        return SessionCompleteResponse(
            session_id=recent.id,
            overall_score=recent.overall_score or 0,
            completed_at=recent.completed_at,
            mastery_updates=[],
        )
    
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
    cefr_level = profile.target_cefr_level if profile else "A1"
    words = crud_vocab.get_day_words(db, cycle=cycle, day=session_data.day_number, target_cefr_level=cefr_level)
    
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
    failed: List[ReviewWordFailure] = []
    
    for item in submission.reviews:
        try:
            previous_uv = db.query(crud_vocab.UserVocabulary).filter(
                crud_vocab.UserVocabulary.id == item.user_vocab_id,
                crud_vocab.UserVocabulary.user_id == current_user.id,
            ).first()
            prev_level = previous_uv.mastery_level if previous_uv else 1
            
            uv = crud_vocab.update_user_vocabulary_mastery(
                db, user_id=current_user.id, user_vocab_id=item.user_vocab_id, is_correct=item.is_correct
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
        except ValueError:
            # Record doesn't exist or isn't owned by this user
            failed.append(ReviewWordFailure(user_vocab_id=item.user_vocab_id, reason="not_found"))
        except Exception as e:
            logger.error(f"Failed to update review for user_vocab_id={item.user_vocab_id}: {e}", exc_info=True)
            db.rollback()  # clear any aborted transaction so remaining items can proceed
            failed.append(ReviewWordFailure(user_vocab_id=item.user_vocab_id, reason="internal_error"))
            
    return ReviewSubmissionResult(updated_words=updated_words, failed=failed)


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
    suggestion = db.query(crud_vocab.PersonalizedVocabSuggestion).filter(
        crud_vocab.PersonalizedVocabSuggestion.id == id
    ).first()
    
    if not suggestion or suggestion.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )
        
    suggestion = crud_vocab.update_suggestion_status(db, suggestion_id=id, new_status=status_update)
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
