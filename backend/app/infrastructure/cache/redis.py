"""Redis-backed fixed-window counters used for auth throttling."""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import RateLimitedError

logger = logging.getLogger(__name__)

_client: Redis | None = None


def get_redis_client() -> Redis:
    """Return the process-wide async client; no connection is made here."""

    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis_client() -> None:
    """Release the pooled connections (called from application shutdown)."""

    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def enforce_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    """Increment ``key`` and raise 429 once the window budget is spent.

    Fails open when Redis is unreachable: throttling is defence in depth, not a
    precondition for authentication, and the failure is logged for alerting.
    """

    if not settings.rate_limit_enabled or limit <= 0:
        return

    try:
        client = get_redis_client()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        if count > limit:
            ttl = await client.ttl(key)
            raise RateLimitedError(
                "Too many requests. Try again later.",
                retry_after=ttl if ttl and ttl > 0 else window_seconds,
            )
    except RateLimitedError:
        raise
    except Exception:  # availability over throttling
        logger.warning("rate_limit_unavailable key=%s", key, exc_info=True)
