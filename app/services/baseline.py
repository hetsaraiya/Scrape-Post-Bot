"""Baseline scraping service.

On first source creation, performs an initial scrape and marks all current
content as already-seen so future polls only surface genuinely new items.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from app.adapters.registry import AdapterRegistry
from app.models.source_config import SourceConfig

logger = logging.getLogger(__name__)

_PROCESSED_TTL = 2592000  # 30 days
_BASELINE_LIMIT = 50


def _processed_key(source_id: str) -> str:
    return f"processed:{source_id}"


def _source_key(source_id: str) -> str:
    return f"source:{source_id}"


async def perform_baseline_scrape(source_config: SourceConfig, redis: Redis) -> int:
    """Fetch current items and mark them as already-seen without queuing.

    This prevents the first real poll from flooding Phase 3 with historical
    content. Only genuinely new items (published after baseline) will be queued.

    Args:
        source_config: The newly-added source to baseline.
        redis: Connected async Redis client.

    Returns:
        Number of items marked as seen (0 on error).
    """
    logger.info(
        "Starting baseline scrape for source %s (%s)",
        source_config.id,
        source_config.name,
    )

    try:
        adapter = AdapterRegistry.create(source_config)
        items = await adapter.fetch()
    except Exception:
        logger.exception(
            "Baseline fetch failed for source %s — proceeding without baseline",
            source_config.id,
        )
        return 0

    if not items:
        logger.info(f"Source {source_config.id} returned no items during baseline")
        # Still mark baseline complete so polls proceed normally
        await _mark_baseline_complete(source_config, redis)
        return 0

    # Limit to most recent N items to avoid hammering Redis or overwhelming source
    items_to_baseline = items[:_BASELINE_LIMIT]

    processed_key = _processed_key(source_config.id)
    pipeline = redis.pipeline()

    marked = 0
    for item in items_to_baseline:
        if item.url:
            pipeline.sadd(processed_key, item.url)
            marked += 1

    if marked:
        pipeline.expire(processed_key, _PROCESSED_TTL)

    await pipeline.execute()
    await _mark_baseline_complete(source_config, redis)

    logger.info(
        "Baseline complete for source %s: marked %d items as seen",
        source_config.id,
        marked,
    )
    return marked


async def _mark_baseline_complete(source_config: SourceConfig, redis: Redis) -> None:
    """Persist baseline_complete=True on the source config in Redis."""
    source_config.baseline_complete = True
    await redis.set(_source_key(source_config.id), source_config.to_redis())


async def is_item_seen(source_id: str, url: str, redis: Redis) -> bool:
    """Check if a URL has already been seen for this source."""
    return bool(await redis.sismember(_processed_key(source_id), url))


async def mark_items_seen(source_id: str, urls: list[str], redis: Redis) -> None:
    """Mark a batch of URLs as seen for this source (after queuing)."""
    if not urls:
        return
    pipeline = redis.pipeline()
    processed_key = _processed_key(source_id)
    for url in urls:
        pipeline.sadd(processed_key, url)
    pipeline.expire(processed_key, _PROCESSED_TTL)
    await pipeline.execute()
