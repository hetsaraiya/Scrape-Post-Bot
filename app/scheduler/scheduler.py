"""APScheduler wrapper with FastAPI lifespan integration."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_source_scheduler: "SourceScheduler | None" = None


def get_scheduler() -> AsyncIOScheduler:
    """Return global scheduler instance, creating if not yet initialized."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={"coalesce": True, "max_instances": 1},
        )
    return _scheduler


def get_source_scheduler() -> "SourceScheduler":
    """Return the active SourceScheduler instance.

    Raises:
        RuntimeError: If scheduler has not been initialized.
    """
    if _source_scheduler is None:
        raise RuntimeError("SourceScheduler not initialized. Call init_scheduler() first.")
    return _source_scheduler


async def init_scheduler(redis_client: aioredis.Redis) -> AsyncIOScheduler:
    """Start scheduler and load active sources from Redis.

    Args:
        redis_client: Connected async Redis client.

    Returns:
        Started AsyncIOScheduler instance.
    """
    global _source_scheduler

    from app.models.source_config import SourceConfig
    from app.scheduler.jobs import SourceScheduler

    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    source_scheduler = SourceScheduler(scheduler)
    _source_scheduler = source_scheduler

    # Load active sources from Redis
    keys = await redis_client.keys("source:*")
    loaded = 0
    for key in keys:
        try:
            raw = await redis_client.get(key)
            if raw is None:
                continue
            config = SourceConfig.from_redis(raw)
            if config.is_active:
                source_scheduler.add_source(config)
                loaded += 1
        except Exception:
            logger.exception(f"Failed to load source from Redis key {key}")

    logger.info(f"Loaded {loaded} active sources into scheduler")
    return scheduler


async def shutdown_scheduler() -> None:
    """Cleanly stop the scheduler."""
    global _scheduler, _source_scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")
    _scheduler = None
    _source_scheduler = None


@asynccontextmanager
async def scheduler_lifespan(redis_client: aioredis.Redis) -> AsyncGenerator[None, None]:
    """Context manager for scheduler startup/shutdown in FastAPI lifespan."""
    await init_scheduler(redis_client)
    try:
        yield
    finally:
        await shutdown_scheduler()
