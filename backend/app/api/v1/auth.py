from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError

from app.core import security
from app.api import deps
from app.crud import user as crud_user
from app.crud import token as crud_token
from app.db.models.user import User
from app.db.models.enums import OAuthProvider
from app.services.google_oauth import verify_google_id_token, GoogleAuthError
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    GoogleOAuthCallback,
    GoogleUserInfo,
    TokenResponse,
    TokenRefreshRequest,
    LogoutRequest,
    LogoutResponse,
    UserResponse,
    UserProfileUpdate,
    LearningProfileCreate,
    LearningProfileResponse,
    OnboardingCompleteResponse,
)

router = APIRouter()


def _issue_token_pair(db: Session, user: User) -> dict:
    """
    Issue an access/refresh token pair, persisting the refresh token's jti
    server-side so it can be rotated and revoked.
    """
    access_token = security.create_access_token(user.id)
    refresh_token, jti, expires_at = security.create_refresh_token(user.id)
    crud_token.store_refresh_token(db, jti=jti, user_id=user.id, expires_at=expires_at)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


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
    
    return _issue_token_pair(db, user)


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
    return _issue_token_pair(db, user)


@router.post("/google", response_model=TokenResponse)
def login_google(
    oauth_data: GoogleOAuthCallback, db: Session = Depends(deps.get_db)
) -> Any:
    """
    Google OAuth authentication. Verifies the Google ID token server-side
    (signature, audience, issuer, expiry, email_verified) before trusting
    any identity claims. Creates or links the user account.
    """
    try:
        claims = verify_google_id_token(oauth_data.id_token)
    except GoogleAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    google_user = GoogleUserInfo(
        email=claims["email"],
        oauth_provider_id=claims["sub"],
        first_name=claims.get("given_name"),
        last_name=claims.get("family_name"),
        avatar_url=claims.get("picture"),
    )

    user = crud_user.get_user_by_email(db, email=google_user.email)
    if user:
        if user.oauth_provider == OAuthProvider.GOOGLE and user.oauth_provider_id != google_user.oauth_provider_id:
            # Same email but a different Google account identity — do not link.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google account does not match the linked account",
            )
        # Link OAuth provider if not already set
        if not user.oauth_provider:
            user.oauth_provider = OAuthProvider.GOOGLE
            user.oauth_provider_id = google_user.oauth_provider_id
            if google_user.avatar_url and not user.avatar_url:
                user.avatar_url = google_user.avatar_url
            db.add(user)
            db.commit()
            db.refresh(user)
    else:
        user = crud_user.create_oauth_user(db, oauth_data=google_user)
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive account",
        )
        
    crud_user.update_last_login(db, user=user)
    return _issue_token_pair(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    refresh_request: TokenRefreshRequest, db: Session = Depends(deps.get_db)
) -> Any:
    """
    Rotate the refresh token: the presented token is single-use. A valid
    token is revoked and exchanged for a fresh access/refresh pair. If a
    previously used (revoked) token is presented again, all of the user's
    sessions are revoked (token theft / replay protection).
    """
    try:
        payload = security.decode_token(refresh_request.refresh_token)
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        jti_str: str = payload.get("jti")
        if user_id_str is None or jti_str is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token signature",
        )

    try:
        jti = uuid.UUID(jti_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    token_record = crud_token.get_refresh_token(db, jti=jti)
    if not token_record or str(token_record.user_id) != user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is not recognized",
        )
    if token_record.revoked_at is not None:
        # Reuse of a rotated/revoked token indicates possible theft:
        # revoke every active session for this user.
        crud_token.revoke_all_user_tokens(db, user_id=token_record.user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    user = crud_user.get_user_by_id(db, user_id=user_id_str)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or inactive",
        )

    access_token = security.create_access_token(user.id)
    new_refresh_token, new_jti, expires_at = security.create_refresh_token(user.id)
    crud_token.rotate_refresh_token(
        db, old_token=token_record, new_jti=new_jti, expires_at=expires_at
    )
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout", response_model=LogoutResponse)
def logout(
    logout_request: LogoutRequest, db: Session = Depends(deps.get_db)
) -> Any:
    """
    Revoke the presented refresh token (or all of the user's sessions when
    `all_sessions` is true). Idempotent: an already-revoked token succeeds.
    """
    try:
        payload = security.decode_token(logout_request.refresh_token)
        if payload.get("type") != "refresh" or not payload.get("jti"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        jti = uuid.UUID(payload["jti"])
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    token_record = crud_token.get_refresh_token(db, jti=jti)
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is not recognized",
        )

    if logout_request.all_sessions:
        revoked = crud_token.revoke_all_user_tokens(db, user_id=token_record.user_id)
        return {"detail": "All sessions revoked", "sessions_revoked": revoked}

    if token_record.revoked_at is None:
        crud_token.revoke_refresh_token(db, token_record)
        return {"detail": "Logged out", "sessions_revoked": 1}
    return {"detail": "Logged out", "sessions_revoked": 0}


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
