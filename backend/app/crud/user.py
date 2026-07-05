import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.user import User, UserLearningProfile
from app.db.models.enums import OAuthProvider
from app.schemas.auth import UserRegister, UserProfileUpdate, LearningProfileCreate, GoogleOAuthCallback


def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]:
    """
    Retrieve a user from the database by their ID.
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Retrieve a user from the database by their email.
    """
    return db.query(User).filter(User.email == email.lower().strip()).first()


def create_user(db: Session, user_data: UserRegister) -> User:
    """
    Create a new local email/password user in the database.
    """
    hashed_pwd = hash_password(user_data.password)
    user = User(
        email=user_data.email.lower().strip(),
        hashed_password=hashed_pwd,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_oauth_user(db: Session, oauth_data: GoogleOAuthCallback) -> User:
    """
    Create a new user with Google OAuth credentials.
    """
    user = User(
        email=oauth_data.email.lower().strip(),
        first_name=oauth_data.first_name,
        last_name=oauth_data.last_name,
        avatar_url=oauth_data.avatar_url,
        oauth_provider=OAuthProvider.GOOGLE,
        oauth_provider_id=oauth_data.oauth_provider_id,
        hashed_password=None,  # No password for OAuth users
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, update_data: UserProfileUpdate) -> User:
    """
    Update basic user profile details.
    """
    if update_data.first_name is not None:
        user.first_name = update_data.first_name
    if update_data.last_name is not None:
        user.last_name = update_data.last_name
    if update_data.avatar_url is not None:
        user.avatar_url = update_data.avatar_url
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_last_login(db: Session, user: User) -> None:
    """
    Update the last login timestamp for the user.
    """
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()


def create_learning_profile(
    db: Session, user_id: uuid.UUID, profile_data: LearningProfileCreate
) -> UserLearningProfile:
    """
    Create a learning profile for the user, mapping their learning state.
    """
    profile = UserLearningProfile(
        user_id=user_id,
        current_cycle=1,
        current_day=1,
        goal=profile_data.goal,
        target_cefr_level=profile_data.target_cefr_level,
        native_language=profile_data.native_language,
        timezone=profile_data.timezone,
        daily_reminder_enabled=profile_data.daily_reminder_enabled,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_learning_profile(db: Session, user_id: uuid.UUID) -> Optional[UserLearningProfile]:
    """
    Retrieve the learning profile for a user.
    """
    return db.query(UserLearningProfile).filter(UserLearningProfile.user_id == user_id).first()


def update_learning_profile(
    db: Session, user_id: uuid.UUID, update_data: dict
) -> Optional[UserLearningProfile]:
    """
    Update existing learning profile values for a user.
    """
    profile = get_learning_profile(db, user_id)
    if not profile:
        return None
    
    for key, value in update_data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
            
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def mark_onboarding_completed(db: Session, user: User) -> User:
    """
    Flag onboarding as completed for the user.
    """
    user.onboarding_completed = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
