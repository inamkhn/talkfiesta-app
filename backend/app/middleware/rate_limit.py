import logging
import redis
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.api import deps
from app.db.models.user import User

logger = logging.getLogger("app.middleware.rate_limit")

# Lazy connection client
redis_client = None
if settings.REDIS_URL:
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning(f"Failed to initialize Redis client with URL {settings.REDIS_URL}: {e}")

# In-memory storage fallback mapping user_id (string) to daily tracking dict:
# { "count": X, "last_reset": datetime }
ai_usage_registry = {}


def check_ai_rate_limit(
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    """
    Dependency check to enforce daily limits on AI evaluation endpoints,
    protecting against cost overrun and abuse. (Capped at 50 per day for dev/MVP).
    Uses Redis with an automatic fallback to local memory in case Redis is offline.
    """
    MAX_DAILY_AI_CALLS = 50
    user_id = str(current_user.id)
    redis_success = False

    if redis_client is not None:
        try:
            key = f"rate_limit:ai:{user_id}"
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, 86400)
            
            if count > MAX_DAILY_AI_CALLS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily evaluation limit reached. Please wait 24 hours to resume AI grading.",
                )
            redis_success = True
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Redis rate limiting failed: {e}. Falling back to in-memory rate limiter.")
            redis_success = False

    if not redis_success:
        now = datetime.now(timezone.utc)
        
        # Check/initialize usage record
        record = ai_usage_registry.get(user_id)
        if not record:
            record = {"count": 0, "last_reset": now}
            ai_usage_registry[user_id] = record
            
        # Reset limit if 24 hours have passed since last reset
        elapsed = now - record["last_reset"]
        if elapsed.total_seconds() >= 86400:
            record["count"] = 0
            record["last_reset"] = now
            
        if record["count"] >= MAX_DAILY_AI_CALLS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily evaluation limit reached. Please wait 24 hours to resume AI grading.",
            )
            
        record["count"] += 1
