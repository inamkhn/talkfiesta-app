import uuid
import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models.speaking import SpeakingSubmission, LiveConversationSession
from app.db.models.enums import SubmissionStatus, LiveSessionStatus
from app.crud.speaking import update_submission, update_live_session
from app.services.speaking_evaluator import process_transcript_evaluation

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.speaking_tasks.process_speaking_submission")
def process_speaking_submission(submission_id: str) -> None:
    """
    Task to evaluate a Flow A (Scripted) speaking submission.
    Mocks STT since Deepgram is skipped for now, computes audio metrics,
    and runs the AI feedback pipeline.
    """
    logger.info(f"Processing speaking submission {submission_id}")
    db = SessionLocal()
    
    try:
        sub_uuid = uuid.UUID(submission_id)
        submission = db.query(SpeakingSubmission).filter(SpeakingSubmission.id == sub_uuid).first()
        
        if not submission:
            logger.error(f"Submission not found: {submission_id}")
            return
        
        # 1. Mock Speech-to-Text
        mock_transcript = "This is a mocked transcript since STT is currently bypassed. I am speaking English to practice."
        word_count = len(mock_transcript.split())
        duration_seconds = 15
        pause_count = 2
        filler_words_count = 1
        
        # Update submission with STT details
        submission.transcript = mock_transcript
        submission.duration_seconds = duration_seconds
        submission.word_count = word_count
        submission.words_per_minute = (word_count / duration_seconds) * 60
        submission.pause_count = pause_count
        submission.filler_words_count = filler_words_count
        db.commit()
        
        # 2. AI Evaluation Pipeline
        feedback = process_transcript_evaluation(
            transcript=mock_transcript,
            duration_sec=duration_seconds,
            word_count=word_count,
            pause_count=pause_count,
            filler_words_count=filler_words_count
        )
        
        # 3. Update Database
        submission.fluency_score = feedback["fluency_score"]
        submission.grammar_score = feedback["grammar_score"]
        submission.vocabulary_score = feedback["vocabulary_score"]
        submission.overall_score = feedback["overall_score"]
        submission.grammar_corrections = feedback["grammar_corrections"]
        submission.vocabulary_suggestions = feedback["vocabulary_suggestions"]
        submission.ai_feedback = feedback["ai_feedback"]
        submission.status = SubmissionStatus.COMPLETED
        submission.completed_at = datetime.now(timezone.utc)
        
        db.commit()
        logger.info(f"Successfully processed speaking submission {submission_id}")
        
    except Exception as exc:
        logger.error(f"Error processing speaking submission {submission_id}: {exc}", exc_info=True)
        try:
            sub = db.query(SpeakingSubmission).filter(SpeakingSubmission.id == uuid.UUID(submission_id)).first()
            if sub:
                sub.status = SubmissionStatus.FAILED
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@celery_app.task(name="app.workers.speaking_tasks.process_live_session_analysis")
def process_live_session_analysis(session_id: str) -> None:
    """
    Task to evaluate a Flow B (Live Conversation) session.
    Takes the aggregated transcript from the session and runs the AI feedback pipeline.
    Creates/Updates a linked SpeakingSubmission to store the scores.
    """
    logger.info(f"Processing live session analysis {session_id}")
    db = SessionLocal()
    
    try:
        sess_uuid = uuid.UUID(session_id)
        live_session = db.query(LiveConversationSession).filter(LiveConversationSession.id == sess_uuid).first()
        
        if not live_session:
            logger.error(f"Live session not found: {session_id}")
            return
            
        transcript_turns = live_session.transcript_json or []
        # Filter to only the user's turns for scoring
        user_turns = [turn["text"] for turn in transcript_turns if turn.get("speaker", "").lower() == "user"]
        full_user_transcript = " ".join(user_turns)
        
        if not full_user_transcript:
            logger.warning(f"No user transcript found for live session {session_id}")
            full_user_transcript = "User said nothing."
            
        word_count = len(full_user_transcript.split())
        duration_seconds = live_session.actual_duration_seconds or 60
        pause_count = 0  # Hard to accurately measure from live text stream without raw audio gaps
        filler_words_count = sum(full_user_transcript.lower().split().count(f) for f in ["um", "uh", "like"])
        
        # 1. AI Evaluation Pipeline
        feedback = process_transcript_evaluation(
            transcript=full_user_transcript,
            duration_sec=duration_seconds,
            word_count=word_count,
            pause_count=pause_count,
            filler_words_count=filler_words_count
        )
        
        # 2. Create/Update linked SpeakingSubmission
        submission = SpeakingSubmission(
            user_id=live_session.user_id,
            exercise_id=None,
            audio_url="live_session_audio",
            transcript=full_user_transcript,
            duration_seconds=duration_seconds,
            word_count=word_count,
            words_per_minute=(word_count / duration_seconds) * 60 if duration_seconds > 0 else 0,
            pause_count=pause_count,
            filler_words_count=filler_words_count,
            fluency_score=feedback["fluency_score"],
            grammar_score=feedback["grammar_score"],
            vocabulary_score=feedback["vocabulary_score"],
            overall_score=feedback["overall_score"],
            grammar_corrections=feedback.get("grammar_corrections"),
            vocabulary_suggestions=feedback.get("vocabulary_suggestions"),
            ai_feedback=feedback.get("ai_feedback"),
            status=SubmissionStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc)
        )
        db.add(submission)
        db.flush()
        
        live_session.submission_id = submission.id
        live_session.topic_relevance_score = feedback["overall_score"]
        live_session.status = LiveSessionStatus.ENDED
        
        db.commit()
        logger.info(f"Successfully processed live session {session_id}")
        
    except Exception as exc:
        logger.error(f"Error processing live session {session_id}: {exc}", exc_info=True)
        try:
            sess = db.query(LiveConversationSession).filter(LiveConversationSession.id == uuid.UUID(session_id)).first()
            if sess:
                sess.status = LiveSessionStatus.ERROR
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
