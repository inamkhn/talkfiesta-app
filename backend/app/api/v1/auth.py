from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError

from app.core import security
from app.api import deps
from app.crud import user as crud_user
from app.db.models.user import User
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    GoogleOAuthCallback,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse,
    UserProfileUpdate,
    LearningProfileCreate,
    LearningProfileResponse,
    OnboardingCompleteResponse,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(deps.get_db)) -> Any:
    """
    Register a new user with email and password.
    """
    user = crud_user.get_user_by_email(db, email=user_data.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = crud_user.create_user(db, user_data=user_data)
    crud_user.update_last_login(db, user=user)
    
    access_token = security.create_access_token(user.id)
    refresh_token = security.create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(deps.get_db)
) -> Any:
    """
    OAuth2 compatible token login, retrieve access and refresh tokens.
    Uses username field as email.
    """
    user = crud_user.get_user_by_email(db, email=form_data.username)
    if not user or not user.hashed_password or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive account",
        )
        
    crud_user.update_last_login(db, user=user)
    access_token = security.create_access_token(user.id)
    refresh_token = security.create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/google", response_model=TokenResponse)
def login_google(
    oauth_data: GoogleOAuthCallback, db: Session = Depends(deps.get_db)
) -> Any:
    """
    Google OAuth authentication callback. Verifies/creates user.
    """
    user = crud_user.get_user_by_email(db, email=oauth_data.email)
    if user:
        # Link OAuth provider if not already set
        if not user.oauth_provider:
            user.oauth_provider = oauth_data.oauth_provider
            user.oauth_provider_id = oauth_data.oauth_provider_id
            if oauth_data.avatar_url and not user.avatar_url:
                user.avatar_url = oauth_data.avatar_url
            db.add(user)
            db.commit()
            db.refresh(user)
    else:
        user = crud_user.create_oauth_user(db, oauth_data=oauth_data)
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive account",
        )
        
    crud_user.update_last_login(db, user=user)
    access_token = security.create_access_token(user.id)
    refresh_token = security.create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    refresh_request: TokenRefreshRequest, db: Session = Depends(deps.get_db)
) -> Any:
    """
    Refresh access and refresh tokens using a valid refresh token.
    """
    try:
        payload = security.decode_token(refresh_request.refresh_token)
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id_str is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token signature",
        )
        
    user = crud_user.get_user_by_id(db, user_id=user_id_str)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or inactive",
        )
        
    access_token = security.create_access_token(user.id)
    refresh_token = security.create_refresh_token(user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve user metadata for the currently authenticated session.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user(
    update_data: UserProfileUpdate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Update details for the current user's profile.
    """
    user = crud_user.update_user(db, user=current_user, update_data=update_data)
    return user


@router.post("/onboarding/learning-profile", response_model=LearningProfileResponse)
def configure_learning_profile(
    profile_data: LearningProfileCreate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Set up or update a user's CEFR level and learning goals.
    """
    existing_profile = crud_user.get_learning_profile(db, user_id=current_user.id)
    if existing_profile:
        # Update existing profile
        update_dict = profile_data.model_dump(exclude_unset=True)
        profile = crud_user.update_learning_profile(db, user_id=current_user.id, update_data=update_dict)
    else:
        # Create new profile
        profile = crud_user.create_learning_profile(db, user_id=current_user.id, profile_data=profile_data)
    return profile


@router.post("/onboarding/complete", response_model=OnboardingCompleteResponse)
def complete_onboarding(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Finalize onboarding, marking the user's initial state configuration complete.
    """
    profile = crud_user.get_learning_profile(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Learning profile must be configured before onboarding can be completed.",
        )
    user = crud_user.mark_onboarding_completed(db, user=current_user)
    return {
        "user": user,
        "learning_profile": profile,
    }
