from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Any
from datetime import datetime, timezone

from app.api.deps import get_db
from app.api.deps import get_current_user
from app.middleware.rate_limit import check_ai_rate_limit
from app.db.models.user import User
from app.db.models.enums import AgentType, InterviewMode, PanelSessionStatus

from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewStartResponse,
    InterviewTurnCreate,
    InterviewTurnResponse,
    InterviewSessionResponse
)
from app.crud.interview import (
    create_interview_session,
    get_interview_session,
    update_interview_session,
    create_panel_response,
    get_active_panel_round
)
from app.services.interview_orchestrator import (
    PanelSessionState,
    process_interview_turn
)

router = APIRouter()

@router.post("/start", response_model=InterviewStartResponse)
def start_interview_session(
    session_in: InterviewSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(check_ai_rate_limit)
) -> Any:
    """
    Initialize a new Multi-Agent Interview Panel session.
    Returns the session ID and the opening question from the first agent.
    """
    db_session = create_interview_session(db, user_id=current_user.id, obj_in=session_in)
    
    # Initialize LangGraph state
    initial_agent = session_in.selected_agent_type.value if session_in.interview_mode == InterviewMode.SINGLE_AGENT else AgentType.HR.value
    
    state: PanelSessionState = {
        "session_id": str(db_session.id),
        "domain": session_in.domain.value,
        "level": session_in.level.value,
        "role": session_in.role,
        "company_style": session_in.company_style.value if session_in.company_style else None,
        "interview_mode": session_in.interview_mode.value,
        "selected_agent_type": session_in.selected_agent_type.value if session_in.selected_agent_type else None,
        "target_duration_minutes": session_in.target_duration_minutes,
        "session_start_time_iso": datetime.now(timezone.utc).isoformat(),
        "current_round": "1",
        "current_agent": initial_agent,
        "topics_asked": [],
        "transcript": [],
        "questions_asked_this_round": 0,
        "round_start_time_iso": datetime.now(timezone.utc).isoformat(),
        "wildcards_used": 0,
        "end_reason": None,
        "next_question_text": None,
        "reaction_text": None,
        "next_agent_for_ui": None,
        "is_closing": False
    }
    
    # Run the first turn through the orchestrator to get the opening question
    updated_state = process_interview_turn(state)
    
    # Persist updated state to DB
    update_interview_session(db, db_session, {"session_state": updated_state})
    
    return {
        "session_id": db_session.id,
        "initial_question": updated_state.get("next_question_text", "Hello, let's begin!"),
        "agent": updated_state.get("current_agent"),
        "current_round": updated_state.get("current_round"),
        "remaining_minutes": session_in.target_duration_minutes
    }

@router.post("/{session_id}/turn", response_model=InterviewTurnResponse)
def process_turn(
    session_id: UUID,
    turn_in: InterviewTurnCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rate_limit: None = Depends(check_ai_rate_limit)
) -> Any:
    """
    Process a single turn. The user sends their transcript, the AI responds and routes.
    """
    db_session = get_interview_session(db, session_id=session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if db_session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if db_session.status != PanelSessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Interview session is not active")
        
    state: PanelSessionState = db_session.session_state
    
    # 1. Log the user's answer into the state transcript
    state["transcript"].append({
        "speaker": "Candidate",
        "text": turn_in.transcript,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # 2. Process via LangGraph Orchestrator
    updated_state = process_interview_turn(state)
    
    # 3. Log the AI's question into the state transcript for the next turn
    if updated_state.get("next_question_text"):
        updated_state["transcript"].append({
            "speaker": updated_state["current_agent"],
            "text": updated_state["next_question_text"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    # 4. Save to PanelResponse for permanent record
    panel_round = get_active_panel_round(
        db, 
        session_id=session_id, 
        agent_type=AgentType(updated_state["current_agent"]), 
        round_number=int(updated_state["current_round"]) if updated_state["current_round"].isdigit() else 1
    )
    
    create_panel_response(
        db,
        round_id=panel_round.id,
        question_text=state.get("next_question_text", ""), # The question that was just answered
        user_answer_transcript=turn_in.transcript,
        agent_reaction_text=updated_state.get("reaction_text")
    )
    
    # 5. Check if session ended
    if updated_state.get("is_closing"):
        db_session.status = PanelSessionStatus.ENDED
        db_session.ended_at = datetime.now(timezone.utc)
        start_time = datetime.fromisoformat(updated_state["session_start_time_iso"])
        db_session.actual_duration_minutes = int((datetime.now(timezone.utc) - start_time).total_seconds() / 60.0)
        db_session.end_reason = updated_state.get("end_reason")
        
        # Enqueue Celery Task for Post-Session Evaluation
        from app.workers.interview_tasks import process_interview_report
        process_interview_report.delay(str(db_session.id))
        
    # Persist updated state to DB
    update_interview_session(db, db_session, {"session_state": updated_state})
    
    # Calculate remaining minutes
    start_time = datetime.fromisoformat(updated_state["session_start_time_iso"])
    elapsed_minutes = (datetime.now(timezone.utc) - start_time).total_seconds() / 60.0
    remaining_minutes = max(0, int(updated_state["target_duration_minutes"] - elapsed_minutes))
    
    return {
        "reaction_text": updated_state.get("reaction_text"),
        "next_question": updated_state.get("next_question_text"),
        "next_agent": updated_state.get("next_agent_for_ui"),
        "current_round": updated_state.get("current_round"),
        "remaining_minutes": remaining_minutes,
        "is_closing": updated_state.get("is_closing", False)
    }

@router.get("/{session_id}", response_model=InterviewSessionResponse)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Fetch an interview session.
    """
    db_session = get_interview_session(db, session_id=session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if db_session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    return db_session
