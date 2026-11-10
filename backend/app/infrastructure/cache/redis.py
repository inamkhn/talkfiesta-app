"""Redis-backed fixed-window counters used for auth throttling (supports Redis TCP and Upstash REST)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from redis.asyncio import Redis

from app.core.config import settings
from app.core.exceptions import RateLimitedError

logger = logging.getLogger(__name__)


class UpstashRestRedisClient:
    """Async Upstash Redis HTTP REST client compatible with `redis.asyncio.Redis` rate-limit methods."""

    def __init__(self, rest_url: str, rest_token: str) -> None:
        self._base_url = rest_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {rest_token}",
                "Content-Type": "application/json",
            },
            timeout=5.0,
        )

    async def execute(self, *command: Any) -> Any:
        response = await self._client.post("/", json=list(command))
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return payload.get("result") if isinstance(payload, dict) else None

    async def incr(self, key: str) -> int:
        res = await self.execute("INCR", key)
        return int(res)

    async def expire(self, key: str, seconds: int) -> bool:
        res = await self.execute("EXPIRE", key, int(seconds))
        return bool(res)

    async def ttl(self, key: str) -> int:
        res = await self.execute("TTL", key)
        return int(res)

    async def get(self, key: str) -> str | None:
        res = await self.execute("GET", key)
        return str(res) if res is not None else None

    async def set(
        self, key: str, value: str, *, ex: int | None = None
    ) -> bool:
        if ex is not None:
            res = await self.execute("SET", key, value, "EX", int(ex))
        else:
            res = await self.execute("SET", key, value)
        return res == "OK"

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        res = await self.execute("DEL", *keys)
        return int(res)

    async def aclose(self) -> None:
        await self._client.aclose()


_client: Redis | UpstashRestRedisClient | None = None


def get_redis_client() -> Redis | UpstashRestRedisClient:
    """Return the process-wide async client (Upstash REST if configured, else Redis TCP)."""

    global _client
    if _client is None:
        rest_url = settings.upstash_redis_rest_url.strip()
        rest_token = settings.upstash_redis_rest_token.strip()
        if rest_url and rest_token:
            _client = UpstashRestRedisClient(rest_url, rest_token)
        else:
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
