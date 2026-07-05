import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.db.models.enums import Goal, OAuthProvider


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleOAuthCallback(BaseModel):
    email: EmailStr
    oauth_provider_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LearningProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    current_cycle: int
    current_day: int
    goal: Goal
    target_cefr_level: str
    native_language: Optional[str] = None
    timezone: str
    daily_reminder_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    oauth_provider: Optional[OAuthProvider] = None
    oauth_provider_id: Optional[str] = None
    onboarding_completed: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    learning_profile: Optional[LearningProfileResponse] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class LearningProfileCreate(BaseModel):
    goal: Goal
    target_cefr_level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$")
    native_language: Optional[str] = None
    timezone: str = "UTC"
    daily_reminder_enabled: bool = True


class OnboardingCompleteResponse(BaseModel):
    user: UserResponse
    learning_profile: LearningProfileResponse
