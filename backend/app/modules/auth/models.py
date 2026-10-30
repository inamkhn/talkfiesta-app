"""Identity models: accounts (V4 consolidated user + onboarding/preferences) and refresh sessions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base

USER_ROLES = ("LEARNER", "CONTENT_REVIEWER", "ADMIN")
ONBOARDING_STATUSES = (
    "NOT_STARTED",
    "PREFERENCES_SAVED",
    "ASSESSING",
    "RESULT_READY",
    "COMPLETED",
)


class User(Base):
    """A registered TalkFiesta account with consolidated profile, preferences and onboarding state."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('LEARNER','CONTENT_REVIEWER','ADMIN')", name="role"),
        CheckConstraint(
            "onboarding_status IN ('NOT_STARTED','PREFERENCES_SAVED','ASSESSING','RESULT_READY','COMPLETED')",
            name="onboarding_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Always stored lowercased; uniqueness is enforced by ``ix_users_email_lower``.
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    # Null for Google-only accounts.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Verified Google subject identifier; never linked by unverified email alone.
    google_sub: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="LEARNER")
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    onboarding_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="NOT_STARTED"
    )
    current_cefr: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Bumped on password reset to invalidate every outstanding access token.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def hashed_password(self) -> str | None:
        return self.password_hash

    @hashed_password.setter
    def hashed_password(self, value: str | None) -> None:
        self.password_hash = value

    @property
    def first_name(self) -> str | None:
        return self.display_name

    @first_name.setter
    def first_name(self, value: str | None) -> None:
        self.display_name = value

    @property
    def onboarding_completed(self) -> bool:
        return self.onboarding_status == "COMPLETED"

    @onboarding_completed.setter
    def onboarding_completed(self, value: bool) -> None:
        self.onboarding_status = "COMPLETED" if value else "NOT_STARTED"


Index("ix_users_email_lower", func.lower(User.email), unique=True)


class AuthSession(Base):
    """A single-use refresh-token session.

    Every refresh rotates the token: the presented row is revoked with reason
    ``ROTATED`` and its successor records ``rotated_from_id``. Presenting an
    already-revoked token is treated as theft and revokes the whole
    ``family_id`` chain.
    """

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint(
            "revoked_reason IS NULL OR revoked_reason IN "
            "('LOGOUT','ROTATED','REUSE_DETECTED','PASSWORD_RESET','ADMIN')",
            name="revoked_reason",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jti: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
