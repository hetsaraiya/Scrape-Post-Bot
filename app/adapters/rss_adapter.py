"""RSS/Atom feed adapter using feedparser."""

from __future__ import annotations

import asyncio
import logging
from calendar import timegm
from datetime import datetime, timezone
from typing import List

import feedparser
import httpx

from app.adapters.base import SourceAdapter
from app.adapters.registry import AdapterRegistry
from app.infrastructure.rate_limiter import get_rate_limiter
from app.models.content_item import ContentItem
from app.models.source_config import SourceConfig, SourceType

logger = logging.getLogger(__name__)


class RSSAdapter(SourceAdapter):
    """Adapter for fetching and parsing RSS/Atom feeds."""

    def __init__(self, source_config: SourceConfig) -> None:
        super().__init__(source_config)

    def get_poll_interval(self) -> int:
        """Return poll interval in seconds (default 15 minutes)."""
        return self.config.poll_interval or 900

    async def fetch(self) -> List[ContentItem]:
        """Fetch and parse RSS/Atom feed entries into ContentItems."""
        url = self.config.url

        # Apply rate limiting before HTTP request
        rate_limiter = get_rate_limiter()
        await rate_limiter.acquire(url)

        # Fetch feed content
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()

        # Parse in thread pool (feedparser is synchronous)
        feed = await asyncio.to_thread(feedparser.parse, response.text)

        # Log malformed feeds but continue processing
        if feed.bozo:
            logger.warning(
                "Feed %s is malformed: %s",
                url,
                feed.get("bozo_exception", "Unknown"),
            )

        # Parse entries to ContentItems
        items: List[ContentItem] = []
        for entry in feed.entries:
            item = self._parse_entry(entry)
            if item:
                items.append(item)

        logger.info("Fetched %d items from %s", len(items), url)
        return items

    def _parse_entry(self, entry: feedparser.FeedParserDict) -> ContentItem | None:
        """Parse a single feed entry into a ContentItem.

        Returns None if the entry lacks required fields (link/title).
        """
        # Must have at least a link
        link = getattr(entry, "link", None)
        if not link:
            return None

        title = getattr(entry, "title", "Untitled")

        # Extract published date with fallbacks
        published_at = self._parse_date(entry)

        # Extract content with fallbacks
        content = self._extract_content(entry)

        # Generate stable item ID
        item_id = getattr(entry, "id", None) or getattr(entry, "guid", None) or link
        unique_id = f"{self.source_id}:{item_id}"

        return ContentItem(
            id=unique_id,
            source_id=self.source_id,
            url=link,
            title=title,
            content=content,
            published_at=published_at,
        )

    @staticmethod
    def _parse_date(entry: feedparser.FeedParserDict) -> datetime | None:
        """Extract published date from feed entry with fallbacks."""
        for attr in ("published_parsed", "updated_parsed"):
            time_struct = getattr(entry, attr, None)
            if time_struct:
                try:
                    return datetime.fromtimestamp(
                        timegm(time_struct), tz=timezone.utc
                    )
                except (ValueError, OverflowError):
                    continue
        return None

    @staticmethod
    def _extract_content(entry: feedparser.FeedParserDict) -> str:
        """Extract content from feed entry with fallbacks."""
        # Prefer full content (Atom)
        if hasattr(entry, "content") and entry.content:
            return entry.content[0].get("value", "")

        # Fallback to summary
        if hasattr(entry, "summary") and entry.summary:
            return entry.summary

        # Fallback to description (RSS 2.0)
        if hasattr(entry, "description") and entry.description:
            return entry.description

        return ""


# Auto-register on import
AdapterRegistry.register(SourceType.RSS, RSSAdapter)
