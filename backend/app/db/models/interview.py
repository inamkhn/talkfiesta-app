import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, func, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import (
    InterviewDomain,
    InterviewLevel,
    AgentType,
    ReviewStatus,
    WildcardCategory,
    CompanyStyle,
    InterviewMode,
    PanelSessionStatus,
    PanelEndReason,
    OverallVerdict,
    PanelAgentFeedbackType,
)


class DomainQuestionBank(Base):
    __tablename__ = "domain_question_bank"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[InterviewDomain] = mapped_column(
        SQLEnum(InterviewDomain), nullable=False
    )
    level: Mapped[InterviewLevel] = mapped_column(
        SQLEnum(InterviewLevel), nullable=False
    )
    agent_type: Mapped[AgentType] = mapped_column(SQLEnum(AgentType), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    sub_category: Mapped[str] = mapped_column(String, nullable=False)
    expected_answer_notes: Mapped[str] = mapped_column(Text, nullable=False)
    research_grounded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus), nullable=False
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    generation_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_generation_batches.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class WildcardQuestionBank(Base):
    __tablename__ = "wildcard_question_bank"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[WildcardCategory] = mapped_column(
        SQLEnum(WildcardCategory), nullable=False
    )
    suitable_agent_types: Mapped[dict] = mapped_column(
        JSONB, default=list, nullable=False
    )
    min_level: Mapped[InterviewLevel] = mapped_column(
        SQLEnum(InterviewLevel), default=InterviewLevel.ENTRY, nullable=False
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus), nullable=False
    )
    generation_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_generation_batches.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )


class InterviewPanelSession(Base):
    __tablename__ = "interview_panel_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    domain: Mapped[InterviewDomain] = mapped_column(
        SQLEnum(InterviewDomain), nullable=False
    )
    level: Mapped[InterviewLevel] = mapped_column(
        SQLEnum(InterviewLevel), nullable=False
    )
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    company_style: Mapped[CompanyStyle | None] = mapped_column(
        SQLEnum(CompanyStyle), nullable=True
    )
    interview_mode: Mapped[InterviewMode] = mapped_column(
        SQLEnum(InterviewMode), nullable=False
    )
    selected_agent_type: Mapped[AgentType | None] = mapped_column(
        SQLEnum(AgentType), nullable=True
    )
    target_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    wildcards_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[PanelSessionStatus] = mapped_column(
        SQLEnum(PanelSessionStatus), default=PanelSessionStatus.ACTIVE, nullable=False
    )
    end_reason: Mapped[PanelEndReason | None] = mapped_column(
        SQLEnum(PanelEndReason), nullable=True
    )
    overall_verdict: Mapped[OverallVerdict | None] = mapped_column(
        SQLEnum(OverallVerdict), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    rounds = relationship(
        "PanelRound", back_populates="session", cascade="all, delete-orphan"
    )
    feedbacks = relationship(
        "PanelAgentFeedback", back_populates="session", cascade="all, delete-orphan"
    )


class PanelRound(Base):
    __tablename__ = "panel_rounds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_panel_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_type: Mapped[AgentType] = mapped_column(SQLEnum(AgentType), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    questions_asked: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    session = relationship("InterviewPanelSession", back_populates="rounds")
    responses = relationship(
        "PanelResponse", back_populates="round", cascade="all, delete-orphan"
    )


class PanelResponse(Base):
    __tablename__ = "panel_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    round_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("panel_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    user_answer_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    agent_reaction_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str] = mapped_column(String, nullable=False)
    is_wildcard: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    round = relationship("PanelRound", back_populates="responses")


class PanelAgentFeedback(Base):
    __tablename__ = "panel_agent_feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_panel_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_type: Mapped[PanelAgentFeedbackType] = mapped_column(
        SQLEnum(PanelAgentFeedbackType), nullable=False
    )
    score_contribution: Mapped[dict] = mapped_column(JSONB, nullable=False)
    verdict_notes: Mapped[str] = mapped_column(Text, nullable=False)
    best_answer_reference: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("panel_responses.id"), nullable=True
    )
    weakest_answer_reference: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("panel_responses.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    session = relationship("InterviewPanelSession", back_populates="feedbacks")
