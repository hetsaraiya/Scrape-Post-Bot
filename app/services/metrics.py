"""Redis-backed pipeline metrics using atomic hash counters."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import Depends
from pydantic import BaseModel

from app.core.redis import get_redis

METRICS_KEY = "pipeline:metrics"


class PipelineMetrics(BaseModel):
    """Snapshot of pipeline processing counters."""

    items_processed: int = 0
    dedup_hits: int = 0
    eval_passed: int = 0
    eval_failed: int = 0
    gen_success: int = 0
    gen_errors: int = 0


class MetricsService:
    """Atomic counter-based metrics backed by a Redis hash."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def increment(self, field: str, amount: int = 1) -> None:
        """Atomically increment a counter field."""
        await self._redis.hincrby(METRICS_KEY, field, amount)

    async def get_all(self) -> PipelineMetrics:
        """Read all counters and return a typed metrics snapshot."""
        raw: dict[str, str] = await self._redis.hgetall(METRICS_KEY)
        return PipelineMetrics(
            items_processed=int(raw.get("items_processed", 0)),
            dedup_hits=int(raw.get("dedup_hits", 0)),
            eval_passed=int(raw.get("eval_passed", 0)),
            eval_failed=int(raw.get("eval_failed", 0)),
            gen_success=int(raw.get("gen_success", 0)),
            gen_errors=int(raw.get("gen_errors", 0)),
        )

    async def reset(self) -> None:
        """Delete all counters."""
        await self._redis.delete(METRICS_KEY)


def get_metrics_service(
    redis: aioredis.Redis = Depends(get_redis),
) -> MetricsService:
    """FastAPI dependency that provides a MetricsService instance."""
    return MetricsService(redis)
