from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Any
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.config import settings
from app.db.session import get_db
from app.schemas.speaking import (
    LiveConversationSessionCreate,
    LiveConversationSessionTokenResponse,
    LiveConversationSessionEnd,
    LiveConversationSessionResponse
)
from app.crud.speaking import (
    create_live_session,
    get_live_session,
    update_live_session
)
from app.db.models.enums import LiveSessionStatus
from app.workers.speaking_tasks import process_live_session_analysis
from app.api.deps import get_current_user
from app.db.models.user import User

router = APIRouter()

def create_ephemeral_token(user_id: UUID, session_id: UUID) -> str:
    """
    Generates a short-lived JWT token specifically for this live session.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode = {
        "sub": str(user_id),
        "session_id": str(session_id),
        "exp": expire,
        "type": "live_speaking_session"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


@router.post("/session", response_model=LiveConversationSessionTokenResponse)
def start_live_session(
    session_in: LiveConversationSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Create a new live conversation session (Flow B) and return an ephemeral token.
    """
    live_session = create_live_session(db, user_id=current_user.id, obj_in=session_in)
    
    # Generate token
    token = create_ephemeral_token(user_id=current_user.id, session_id=live_session.id)
    
    # Optional: store token issued time in DB
    update_live_session(db, live_session, {"ephemeral_token_issued_at": datetime.now(timezone.utc)})
    
    return {
        "session_id": live_session.id,
        "ephemeral_token": token,
        "ws_endpoint": "wss://api.talkfiesta.com/ws/live"  # Mock endpoint for now
    }

@router.post("/session/{session_id}/end", response_model=LiveConversationSessionResponse)
def end_live_session(
    session_id: UUID,
    end_data: LiveConversationSessionEnd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    End the live conversation session, submit the transcript, and trigger async analysis.
    """
    live_session = get_live_session(db, session_id=session_id)
    if not live_session:
        raise HTTPException(status_code=404, detail="Live session not found")
    if live_session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")
        
    if live_session.status != LiveSessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Live session is not active (already ended or errored).")
        
    transcript_dicts = [t.model_dump() for t in end_data.transcript]
    
    live_session = update_live_session(
        db, 
        live_session, 
        {
            "status": LiveSessionStatus.ENDED,
            "actual_duration_seconds": end_data.actual_duration_seconds,
            "transcript_json": transcript_dicts,
            "turn_count": len(transcript_dicts),
            "ended_at": datetime.now(timezone.utc)
        }
    )
    
    # Enqueue celery job for post-session analysis
    process_live_session_analysis.delay(str(live_session.id))
    
    return live_session

@router.get("/session/{session_id}", response_model=LiveConversationSessionResponse)
def fetch_live_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Fetch the details of a live session.
    """
    live_session = get_live_session(db, session_id=session_id)
    if not live_session:
        raise HTTPException(status_code=404, detail="Live session not found")
    if live_session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return live_session
