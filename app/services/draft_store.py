"""Redis-backed draft storage with sorted set index and TTL."""

from __future__ import annotations

import logging

import redis.asyncio as aioredis
from fastapi import Depends

from app.core.redis import get_redis
from app.models.draft import Draft

logger = logging.getLogger(__name__)

DRAFT_PREFIX = "draft:"
DRAFT_INDEX = "drafts:index"
DRAFT_TTL = 86400 * 30  # 30 days


class DraftStore:
    """Stores and retrieves generated drafts in Redis."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def store(self, draft: Draft) -> None:
        """Store a draft with TTL and add to sorted set index."""
        key = f"{DRAFT_PREFIX}{draft.id}"
        await self._redis.set(key, draft.to_redis(), ex=DRAFT_TTL)
        await self._redis.zadd(
            DRAFT_INDEX,
            {draft.id: draft.created_at.timestamp()},
        )
        logger.debug(f"Stored draft {draft.id}")

    async def get(self, draft_id: str) -> Draft | None:
        """Get a single draft by ID, or None if not found."""
        data = await self._redis.get(f"{DRAFT_PREFIX}{draft_id}")
        if data is None:
            return None
        return Draft.from_redis(data)

    async def list_drafts(self, limit: int = 50, offset: int = 0) -> list[Draft]:
        """List drafts ordered by creation time (newest first)."""
        ids = await self._redis.zrevrange(
            DRAFT_INDEX, offset, offset + limit - 1,
        )
        if not ids:
            return []

        pipe = self._redis.pipeline()
        for draft_id in ids:
            if isinstance(draft_id, bytes):
                draft_id = draft_id.decode("utf-8")
            pipe.get(f"{DRAFT_PREFIX}{draft_id}")
        results = await pipe.execute()

        drafts = []
        for raw in results:
            if raw is not None:
                try:
                    drafts.append(Draft.from_redis(raw))
                except Exception:
                    pass  # Skip corrupted entries
        return drafts


def get_draft_store(
    redis: aioredis.Redis = Depends(get_redis),
) -> DraftStore:
    """FastAPI dependency that provides a DraftStore instance."""
    return DraftStore(redis)
