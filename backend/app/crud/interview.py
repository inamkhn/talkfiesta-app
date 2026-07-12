import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.interview import (
    InterviewPanelSession,
    PanelRound,
    PanelResponse,
    DomainQuestionBank,
    WildcardQuestionBank
)
from app.db.models.enums import (
    PanelSessionStatus,
    InterviewDomain,
    InterviewLevel,
    AgentType,
    WildcardCategory
)
from app.schemas.interview import InterviewSessionCreate

def create_interview_session(
    db: Session, user_id: uuid.UUID, obj_in: InterviewSessionCreate
) -> InterviewPanelSession:
    """
    Creates a new interview panel session.
    """
    db_obj = InterviewPanelSession(
        user_id=user_id,
        domain=obj_in.domain,
        level=obj_in.level,
        role=obj_in.role,
        company_style=obj_in.company_style,
        interview_mode=obj_in.interview_mode,
        selected_agent_type=obj_in.selected_agent_type,
        target_duration_minutes=obj_in.target_duration_minutes,
        status=PanelSessionStatus.ACTIVE
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_interview_session(
    db: Session, session_id: uuid.UUID
) -> Optional[InterviewPanelSession]:
    """
    Fetches an interview session by ID.
    """
    return db.query(InterviewPanelSession).filter(InterviewPanelSession.id == session_id).first()

def update_interview_session(
    db: Session, db_obj: InterviewPanelSession, update_data: Dict[str, Any]
) -> InterviewPanelSession:
    """
    Updates an interview session with partial fields (e.g. state).
    """
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

def get_active_panel_round(
    db: Session, session_id: uuid.UUID, agent_type: AgentType, round_number: int
) -> PanelRound:
    """
    Fetches or creates the current panel round for the session.
    """
    panel_round = db.query(PanelRound).filter(
        PanelRound.session_id == session_id,
        PanelRound.agent_type == agent_type,
        PanelRound.round_number == round_number
    ).first()
    
    if not panel_round:
        panel_round = PanelRound(
            session_id=session_id,
            agent_type=agent_type,
            round_number=round_number
        )
        db.add(panel_round)
        db.commit()
        db.refresh(panel_round)
        
    return panel_round

def create_panel_response(
    db: Session,
    round_id: uuid.UUID,
    question_text: str,
    user_answer_transcript: str,
    agent_reaction_text: Optional[str] = None,
    is_wildcard: bool = False
) -> PanelResponse:
    """
    Logs a single turn in the interview.
    """
    response = PanelResponse(
        round_id=round_id,
        question_text=question_text,
        user_answer_transcript=user_answer_transcript,
        agent_reaction_text=agent_reaction_text,
        audio_url="mocked_audio_for_mvp",
        is_wildcard=is_wildcard
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    return response

def get_domain_questions(
    db: Session, domain: InterviewDomain, level: InterviewLevel, agent_type: AgentType, limit: int = 5
) -> List[DomainQuestionBank]:
    """
    Fetches a pool of pre-generated questions for the Orchestrator to select from.
    """
    return db.query(DomainQuestionBank).filter(
        DomainQuestionBank.domain == domain,
        DomainQuestionBank.level == level,
        DomainQuestionBank.agent_type == agent_type
    ).order_by(func.random()).limit(limit).all()

def get_wildcard_questions(
    db: Session, level: InterviewLevel, agent_type: AgentType, limit: int = 1
) -> List[WildcardQuestionBank]:
    """
    Fetches random curveball questions suitable for the current agent and level.
    """
    # Note: suitable_agent_types is JSONB, so we search if agent_type is in the array.
    # For SQLite mocking (if any) or simplified Postgres, we can do python-side filtering or jsonb containment.
    # Postgres specific:
    return db.query(WildcardQuestionBank).filter(
        WildcardQuestionBank.min_level <= level,
        WildcardQuestionBank.suitable_agent_types.contains([agent_type.value])
    ).order_by(func.random()).limit(limit).all()
