"""Deduplication service for within-source and cross-source duplicate detection."""

from __future__ import annotations

import hashlib
import logging
import re

import redis.asyncio as aioredis

from app.models.content_item import ContentItem

logger = logging.getLogger(__name__)

# TTL for dedup keys: 7 days
_DEDUP_TTL = 604800


class DedupService:
    """Detects duplicate content items using Redis sets."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self.redis = redis

    async def is_duplicate(self, item: ContentItem) -> bool:
        """Check if item is a within-source or cross-source duplicate.

        Does NOT mark the item as processed — call mark_processed() separately.
        """
        source_key = f"dedup:source:{item.source_id}"

        # Within-source: check URL
        if await self.redis.sismember(source_key, item.url):
            logger.debug(f"Within-source duplicate (URL): {item.url}")
            return True

        # Within-source: check content hash
        if item.content_hash and await self.redis.sismember(source_key, item.content_hash):
            logger.debug(f"Within-source duplicate (hash): {item.content_hash}")
            return True

        # Cross-source: check normalized title fingerprint
        fingerprint = self._title_fingerprint(item.title)
        if await self.redis.sismember("dedup:cross_source", fingerprint):
            logger.debug(f"Cross-source duplicate (title): {item.title}")
            return True

        return False

    async def mark_processed(self, item: ContentItem) -> None:
        """Mark an item as processed for future dedup checks."""
        source_key = f"dedup:source:{item.source_id}"

        # Add URL and optional content hash to source set
        await self.redis.sadd(source_key, item.url)
        if item.content_hash:
            await self.redis.sadd(source_key, item.content_hash)
        await self.redis.expire(source_key, _DEDUP_TTL)

        # Add cross-source fingerprint
        fingerprint = self._title_fingerprint(item.title)
        await self.redis.sadd("dedup:cross_source", fingerprint)
        await self.redis.expire("dedup:cross_source", _DEDUP_TTL)

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title: lowercase, strip punctuation, collapse whitespace."""
        title = title.lower()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title)
        return title.strip()

    @classmethod
    def _title_fingerprint(cls, title: str) -> str:
        """Generate a short fingerprint from a normalized title."""
        normalized = cls._normalize_title(title)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
