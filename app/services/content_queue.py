"""Redis-backed FIFO content queue for ingested items."""

from __future__ import annotations

import logging

import orjson
import redis.asyncio as aioredis
from fastapi import Depends

from app.core.redis import get_redis
from app.models.content_item import ContentItem

logger = logging.getLogger(__name__)


class ContentQueue:
    """FIFO queue backed by a Redis list for content items."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        queue_key: str = "content:queue",
    ) -> None:
        self._redis = redis_client
        self._key = queue_key

    async def push(self, item: ContentItem) -> int:
        """Add item to the queue. Returns new queue length."""
        data = item.to_redis()
        length: int = await self._redis.lpush(self._key, data)
        logger.debug(f"Pushed item {item.id} to queue (length={length})")
        return length

    async def pop(self) -> ContentItem | None:
        """Remove and return the oldest item, or None if empty."""
        data = await self._redis.rpop(self._key)
        if data is None:
            return None
        return ContentItem.from_redis(data)

    async def peek(self) -> ContentItem | None:
        """Return the oldest item without removing it, or None if empty."""
        items = await self._redis.lrange(self._key, -1, -1)
        if not items:
            return None
        return ContentItem.from_redis(items[0])

    async def length(self) -> int:
        """Return the number of items in the queue."""
        return await self._redis.llen(self._key)

    async def push_batch(self, items: list[ContentItem]) -> int:
        """Add multiple items efficiently using a pipeline. Returns new length."""
        if not items:
            return await self.length()

        pipe = self._redis.pipeline()
        for item in items:
            pipe.lpush(self._key, item.to_redis())
        await pipe.execute()

        new_length = await self.length()
        logger.debug(f"Pushed {len(items)} items to queue (length={new_length})")
        return new_length


def get_content_queue(
    redis: aioredis.Redis = Depends(get_redis),
) -> ContentQueue:
    """FastAPI dependency that provides a ContentQueue instance."""
    return ContentQueue(redis_client=redis)
