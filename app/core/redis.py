"""Async Redis client with connection pooling."""

import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


async def init_redis(url: str) -> aioredis.Redis:
    """Initialize async Redis client with connection pooling.

    Args:
        url: Redis connection URL (e.g. redis://localhost:6379).

    Returns:
        Connected async Redis client.

    Raises:
        ConnectionError: If Redis is unreachable.
    """
    global _redis_client

    try:
        _redis_client = aioredis.Redis.from_url(
            url,
            decode_responses=True,
            max_connections=20,
        )
        await _redis_client.ping()
        logger.info(f"Redis connected at {url}")
        return _redis_client
    except (aioredis.ConnectionError, OSError) as exc:
        _redis_client = None
        msg = f"Failed to connect to Redis at {url}: {exc}"
        logger.error(msg)
        raise ConnectionError(msg) from exc


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_client

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


def get_redis() -> aioredis.Redis:
    """Return the active Redis client. Used as a FastAPI dependency.

    Raises:
        RuntimeError: If Redis has not been initialized.
    """
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis_client
