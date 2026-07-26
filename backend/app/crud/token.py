import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.user import RefreshToken


def _utcnow() -> datetime:
    """Naive UTC now, consistent with the DateTime columns used across models."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def store_refresh_token(
    db: Session,
    *,
    jti: uuid.UUID,
    user_id: uuid.UUID,
    expires_at: datetime,
) -> RefreshToken:
    """
    Persist the server-side record for a newly issued refresh token.
    """
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    token = RefreshToken(jti=jti, user_id=user_id, expires_at=expires_at)
    db.add(token)
    db.commit()
    return token


def get_refresh_token(db: Session, jti: uuid.UUID) -> Optional[RefreshToken]:
    """
    Retrieve a refresh token record by its jti, locking the row to avoid
    concurrent double-spends during rotation.
    """
    return (
        db.query(RefreshToken)
        .filter(RefreshToken.jti == jti)
        .with_for_update()
        .first()
    )


def rotate_refresh_token(
    db: Session,
    *,
    old_token: RefreshToken,
    new_jti: uuid.UUID,
    expires_at: datetime,
) -> RefreshToken:
    """
    Revoke the presented token and persist its replacement (single-use rotation).
    """
    old_token.revoked_at = _utcnow()
    old_token.replaced_by_jti = new_jti
    db.add(old_token)
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    new_token = RefreshToken(
        jti=new_jti, user_id=old_token.user_id, expires_at=expires_at
    )
    db.add(new_token)
    db.commit()
    return new_token


def revoke_refresh_token(db: Session, token: RefreshToken) -> None:
    """
    Revoke a single refresh token (logout of one session).
    """
    token.revoked_at = _utcnow()
    db.add(token)
    db.commit()


def revoke_all_user_tokens(db: Session, user_id: uuid.UUID) -> int:
    """
    Revoke every active refresh token for a user (logout everywhere /
    token-reuse incident response). Returns the number of tokens revoked.
    """
    count = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .update({RefreshToken.revoked_at: _utcnow()}, synchronize_session=False)
    )
    db.commit()
    return count
