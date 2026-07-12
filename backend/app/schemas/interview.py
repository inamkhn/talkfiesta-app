from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from app.db.models.enums import (
    InterviewDomain,
    InterviewLevel,
    AgentType,
    CompanyStyle,
    InterviewMode,
    PanelSessionStatus,
    PanelEndReason,
    OverallVerdict,
    PanelAgentFeedbackType
)

# ----------------------------------------
# Core Interview Session Setup
# ----------------------------------------
class InterviewSessionCreate(BaseModel):
    domain: InterviewDomain
    level: InterviewLevel
    role: Optional[str] = Field(default=None, max_length=200)
    company_style: Optional[CompanyStyle] = None
    interview_mode: InterviewMode
    selected_agent_type: Optional[AgentType] = None
    target_duration_minutes: int = Field(default=15, le=30, gt=0)

    @model_validator(mode='after')
    def validate_single_agent_has_type(self):
        if self.interview_mode == InterviewMode.SINGLE_AGENT and self.selected_agent_type is None:
            raise ValueError("selected_agent_type is required when interview_mode is SINGLE_AGENT")
        return self


class InterviewSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    domain: InterviewDomain
    level: InterviewLevel
    role: Optional[str] = None
    company_style: Optional[CompanyStyle] = None
    interview_mode: InterviewMode
    selected_agent_type: Optional[AgentType] = None
    target_duration_minutes: int
    actual_duration_minutes: Optional[int] = None
    wildcards_used: int
    status: PanelSessionStatus
    end_reason: Optional[PanelEndReason] = None
    overall_verdict: Optional[OverallVerdict] = None
    started_at: datetime
    ended_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------
# Turn-based Orchestrator Schemas
# ----------------------------------------
class InterviewTurnCreate(BaseModel):
    """
    Since we are mocking STT for the MVP, the client sends raw text.
    """
    transcript: str = Field(..., min_length=1, max_length=5000)


class InterviewTurnResponse(BaseModel):
    reaction_text: Optional[str] = None
    next_question: Optional[str] = None
    next_agent: Optional[AgentType] = None
    current_round: str
    remaining_minutes: int
    is_closing: bool = False
    
class InterviewStartResponse(BaseModel):
    session_id: UUID
    initial_question: str
    agent: AgentType
    current_round: str
    remaining_minutes: int


# ----------------------------------------
# State Machine Tracking Schema
# ----------------------------------------
class PanelSessionStateSchema(BaseModel):
    """
    Internal schema for LangGraph state persistence.
    Stored in `InterviewPanelSession.session_state` JSONB.
    """
    session_id: str
    domain: str
    level: str
    role: Optional[str] = None
    company_style: Optional[str] = None
    interview_mode: str
    selected_agent_type: Optional[str] = None
    target_duration_minutes: int
    session_start_time_iso: str
    current_round: str
    current_agent: str
    topics_asked: List[str] = Field(default_factory=list)
    transcript: List[Dict[str, Any]] = Field(default_factory=list)
    questions_asked_this_round: int = 0
    round_start_time_iso: str
    wildcards_used: int = 0
    end_reason: Optional[str] = None


# ----------------------------------------
# Feedback and Reporting Schemas
# ----------------------------------------
class PanelAgentFeedbackResponse(BaseModel):
    id: UUID
    agent_type: PanelAgentFeedbackType
    score_contribution: Dict[str, Any]
    verdict_notes: str
    best_answer_reference: Optional[UUID] = None
    weakest_answer_reference: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewReportResponse(BaseModel):
    session: InterviewSessionResponse
    feedbacks: List[PanelAgentFeedbackResponse]
