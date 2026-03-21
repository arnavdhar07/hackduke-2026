from __future__ import annotations

from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.config import settings

redis_client: Redis | None = None


async def init_redis() -> None:
    """Create the async Redis client. Called once during app lifespan startup."""
    global redis_client
    redis_client = await redis_from_url(
        settings.redis_url,
        decode_responses=True,
        encoding="utf-8",
    )


async def close_redis() -> None:
    """Close the Redis connection. Called during app lifespan shutdown."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


def get_redis() -> Redis:
    """Return the live Redis client. Raises RuntimeError if called before init_redis()."""
    if redis_client is None:
        raise RuntimeError("Redis client has not been initialised. Call init_redis() first.")
    return redis_client
