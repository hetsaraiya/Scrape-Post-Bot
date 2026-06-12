"""Polling job definitions and SourceScheduler for managing per-source jobs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.adapters.registry import AdapterRegistry
from app.models.content_item import ContentItem
from app.models.source_config import SourceConfig
from app.services.baseline import mark_items_seen
from app.services.content_queue import ContentQueue

logger = logging.getLogger(__name__)


async def poll_source_job(source_config: SourceConfig) -> None:
    """Poll a single source and queue new content items.

    Called by APScheduler for each source at its configured interval.
    Errors are caught and logged — they must not crash the scheduler.
    """
    logger.info(f"Polling source {source_config.id}: {source_config.name}")

    try:
        adapter = AdapterRegistry.create(source_config)
        items = await adapter.fetch()

        if not items:
            logger.debug(f"No new items from {source_config.id}")
            return

        from app.core.redis import get_redis
        redis = get_redis()

        # Filter out items already seen (baseline + previous polls)
        new_items = await _filter_unseen(source_config.id, items, redis)

        if not new_items:
            logger.debug(f"All {len(items)} items from {source_config.id} already seen")
            return

        queue = ContentQueue(redis)
        await queue.push_batch(new_items)
        logger.info(f"Queued {len(new_items)} new items from {source_config.id} ({len(items) - len(new_items)} already seen)")

        # Mark newly queued items as seen
        await mark_items_seen(
            source_config.id,
            [item.url for item in new_items if item.url],
            redis,
        )

    except Exception:
        logger.exception(f"Failed to poll source {source_config.id}")


async def _filter_unseen(
    source_id: str, items: list[ContentItem], redis: "Redis"
) -> list[ContentItem]:
    """Return only items whose URL has not been seen before for this source."""
    if not items:
        return []

    processed_key = f"processed:{source_id}"
    new_items = []
    for item in items:
        if not item.url:
            new_items.append(item)  # No URL to check — pass through
            continue
        already_seen = await redis.sismember(processed_key, item.url)
        if not already_seen:
            new_items.append(item)
    return new_items


class SourceScheduler:
    """Manages APScheduler jobs for monitored sources."""

    def __init__(self, scheduler: AsyncIOScheduler) -> None:
        self.scheduler = scheduler

    def _job_id(self, source_id: str) -> str:
        return f"source_{source_id}"

    def add_source(self, source_config: SourceConfig) -> str:
        """Add an interval polling job for a source.

        Uses replace_existing=True to prevent duplicate jobs on restart.
        Uses max_instances=1 to prevent overlapping runs.
        """
        job_id = self._job_id(source_config.id)
        interval = source_config.poll_interval or 900

        self.scheduler.add_job(
            func=poll_source_job,
            trigger=IntervalTrigger(seconds=interval),
            id=job_id,
            args=[source_config],
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"Scheduled source {source_config.id} every {interval}s (job_id={job_id})")
        return job_id

    def remove_source(self, source_id: str) -> bool:
        """Remove a source's polling job. Returns False if job not found."""
        job_id = self._job_id(source_id)
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job for source {source_id}")
            return True
        except JobLookupError:
            logger.debug(f"Job not found for source {source_id}")
            return False

    def update_source(self, source_config: SourceConfig) -> bool:
        """Update a source's polling interval by removing and re-adding."""
        self.remove_source(source_config.id)
        self.add_source(source_config)
        return True

    def pause_source(self, source_id: str) -> bool:
        """Pause a source's polling job."""
        job_id = self._job_id(source_id)
        try:
            self.scheduler.pause_job(job_id)
            return True
        except JobLookupError:
            return False

    def resume_source(self, source_id: str) -> bool:
        """Resume a paused source's polling job."""
        job_id = self._job_id(source_id)
        try:
            self.scheduler.resume_job(job_id)
            return True
        except JobLookupError:
            return False

    def get_job_state(self, source_id: str) -> str | None:
        """Return job state: 'running', 'paused', or None if not found."""
        job_id = self._job_id(source_id)
        job = self.scheduler.get_job(job_id)
        if job is None:
            return None
        return "paused" if job.next_run_time is None else "running"
