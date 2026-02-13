"""Blog adapter with full-text extraction via trafilatura.

Discovers articles through RSS/Atom feed when available, otherwise falls
back to scraping article links from the HTML listing page.  Full article
text is always extracted using trafilatura.
"""

from __future__ import annotations

import asyncio
import logging
import re
from calendar import timegm
from datetime import datetime, timezone
from typing import List
from urllib.parse import urljoin, urlparse

import feedparser
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from app.adapters.base import SourceAdapter
from app.adapters.registry import AdapterRegistry
from app.core.config import get_settings
from app.infrastructure.rate_limiter import get_rate_limiter
from app.models.content_item import ContentItem
from app.models.source_config import SourceType
from app.services.content_extractor import ContentExtractor

logger = logging.getLogger(__name__)



class BlogAdapter(SourceAdapter):
    """Adapter for blog sources with full-text extraction.

    Strategy (in priority order):
    1. If ``metadata["feed_url"]`` is set, fetch that as RSS/Atom.
    2. Try parsing the source URL itself as RSS/Atom.
    3. Auto-discover a feed <link> tag in the HTML.
    4. Fall back to scraping the HTML listing page for article links.
    """

    def get_poll_interval(self) -> int:
        return self.config.poll_interval or 3600

    # --- Public entry point -----------------------------------------------

    async def fetch(self) -> List[ContentItem]:
        """Fetch blog articles using the best available strategy."""
        url = self.config.url
        raw_text = await self._fetch_page(url)

        # 1. Explicit feed URL in metadata
        feed_url = self.config.metadata.get("feed_url")
        if feed_url:
            items = await self._fetch_via_feed(feed_url)
            if items:
                return items
            logger.info("Explicit feed_url %s yielded no items, falling back", feed_url)

        # 2. Try parsing source URL as RSS/Atom
        feed = await asyncio.to_thread(feedparser.parse, raw_text)
        if not feed.bozo and feed.entries:
            return await self._extract_from_urls(
                [(e.link, e) for e in feed.entries if getattr(e, "link", None)],
                origin=url,
                discovery="rss_atom",
            )

        # 3. Auto-discover feed <link> from HTML
        discovered = self._discover_feed_url(raw_text, url)
        if discovered:
            logger.info("Discovered feed URL %s from HTML <link> tag", discovered)
            items = await self._fetch_via_feed(discovered)
            if items:
                return items

        # 4. Fall back to HTML scraping
        reason = feed.get("bozo_exception", "0 entries") if feed.bozo else "0 entries"
        logger.info("Feed %s not usable (%s), falling back to HTML scraping", url, reason)
        return await self._scrape_html_listing(raw_text, url)

    # --- Shared HTTP helper -----------------------------------------------

    async def _fetch_page(self, url: str) -> str:
        """Fetch a page using browser impersonation and rate limiting."""
        await get_rate_limiter().acquire(url)
        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.get(url, timeout=30.0)
            response.raise_for_status()
        return response.text

    # --- Strategy: RSS/Atom feed ------------------------------------------

    async def _fetch_via_feed(self, feed_url: str) -> List[ContentItem]:
        """Fetch and parse a specific RSS/Atom feed URL."""
        text = await self._fetch_page(feed_url)
        feed = await asyncio.to_thread(feedparser.parse, text)

        if feed.bozo and not feed.entries:
            logger.warning(
                "Feed %s malformed with no entries: %s",
                feed_url, feed.get("bozo_exception", "Unknown"),
            )
            return []

        return await self._extract_from_urls(
            [(e.link, e) for e in feed.entries if getattr(e, "link", None)],
            origin=feed_url,
            discovery="rss_atom",
        )

    # --- Strategy: HTML listing scrape ------------------------------------

    async def _scrape_html_listing(self, html: str, base_url: str) -> List[ContentItem]:
        """Scrape article links from an HTML listing page and extract each."""
        article_urls = self._extract_article_urls(html, base_url)
        if not article_urls:
            logger.warning("No article links found on %s", base_url)
            return []

        new_urls = await self._filter_seen_urls(article_urls)
        skipped = len(article_urls) - len(new_urls)
        if skipped:
            logger.info("Skipping %d/%d already processed articles", skipped, len(article_urls))
        if not new_urls:
            logger.info("No new articles found on %s", base_url)
            return []

        logger.info("Discovered %d new article URLs from %s", len(new_urls), base_url)
        return await self._extract_from_urls(
            [(u, None) for u in new_urls],
            origin=base_url,
            discovery="html_scrape",
        )

    # --- Shared extraction loop -------------------------------------------

    async def _extract_from_urls(
        self,
        url_entries: list[tuple[str, feedparser.FeedParserDict | None]],
        origin: str,
        discovery: str,
    ) -> List[ContentItem]:
        """Extract content from a list of (url, optional_feed_entry) pairs."""
        items: list[ContentItem] = []
        extractor = ContentExtractor()

        for article_url, entry in url_entries:
            content = await extractor.extract_article(
                article_url,
                language=self.config.metadata.get("language"),
                min_length=200,
            )

            if not content:
                logger.debug("Could not extract content from %s", article_url)
                continue

            item = self._build_item(article_url, content, entry, discovery)
            if item:
                items.append(item)

        logger.info("Fetched %d blog articles from %s", len(items), origin)
        return items

    # --- Deduplication ----------------------------------------------------

    async def _filter_seen_urls(self, urls: list[str]) -> list[str]:
        """Filter out URLs already processed (stored in Redis)."""
        from app.core.redis import get_redis

        try:
            processed = await get_redis().smembers(f"processed:{self.source_id}")
            return [u for u in urls if u not in processed]
        except Exception:
            logger.warning("Failed to check processed URLs in Redis", exc_info=True)
            return urls

    # --- URL extraction from HTML -----------------------------------------

    def _extract_article_urls(self, html: str, base_url: str) -> list[str]:
        """Extract unique article URLs from an HTML listing page."""
        settings = get_settings()
        prefixes = tuple(p.strip() for p in settings.ARTICLE_PATH_PREFIXES.split(","))
        max_articles = settings.MAX_HTML_ARTICLES

        soup = BeautifulSoup(html, "html.parser")
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc
        base_path = parsed_base.path.rstrip("/")

        seen: set[str] = set()
        urls: list[str] = []

        for a_tag in soup.find_all("a", href=True):
            full_url = urljoin(base_url, a_tag["href"])
            parsed = urlparse(full_url)

            if parsed.netloc != base_domain:
                continue

            path = parsed.path.rstrip("/")
            if not path or path == base_path:
                continue

            is_subpath = base_path and path.startswith(base_path + "/")
            is_article = any(path.startswith(p.rstrip("/")) for p in prefixes)
            if not (is_subpath or is_article):
                continue

            slug = path.rsplit("/", 1)[-1]
            if len(slug) < 3:
                continue

            canonical = f"{parsed.scheme}://{parsed.netloc}{path}"
            if canonical not in seen:
                seen.add(canonical)
                urls.append(canonical)
                if len(urls) >= max_articles:
                    break

        return urls

    # --- Feed discovery ---------------------------------------------------

    @staticmethod
    def _discover_feed_url(html: str, base_url: str) -> str | None:
        """Look for RSS/Atom <link> tags in the HTML <head>."""
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("link", rel="alternate"):
            link_type = (link.get("type") or "").lower()
            if "rss" in link_type or "atom" in link_type:
                href = link.get("href")
                if href:
                    return urljoin(base_url, href)
        return None

    # --- Item builders ----------------------------------------------------

    def _build_item(
        self,
        url: str,
        content: str,
        entry: feedparser.FeedParserDict | None,
        discovery: str,
    ) -> ContentItem | None:
        """Build a ContentItem from extracted content and optional feed entry."""
        if entry:
            title = getattr(entry, "title", None) or self._title_from_url(url)
            item_id = getattr(entry, "id", None) or getattr(entry, "guid", None) or url
            published_at = self._parse_date(entry)
        else:
            title = self._title_from_url(url)
            item_id = url
            published_at = None

        return ContentItem(
            id=f"{self.source_id}:{item_id}",
            source_id=self.source_id,
            url=url,
            title=title,
            content=content,
            published_at=published_at,
            metadata={
                "extraction_method": "trafilatura",
                "discovery_method": discovery,
                "is_full_text": True,
            },
        )

    @staticmethod
    def _parse_date(entry: feedparser.FeedParserDict) -> datetime | None:
        """Extract published date from feed entry."""
        for attr in ("published_parsed", "updated_parsed"):
            ts = getattr(entry, attr, None)
            if ts:
                try:
                    return datetime.fromtimestamp(timegm(ts), tz=timezone.utc)
                except (ValueError, OverflowError):
                    continue
        return None

    @staticmethod
    def _title_from_url(url: str) -> str:
        """Derive a human-readable title from an article URL slug."""
        path = urlparse(url).path.rstrip("/")
        slug = path.rsplit("/", 1)[-1] if "/" in path else path
        return re.sub(r"[-_]", " ", slug).strip().title() or "Untitled"


# Auto-register on import
AdapterRegistry.register(SourceType.BLOG, BlogAdapter)
