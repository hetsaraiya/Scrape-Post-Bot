"""Blog adapter with full-text extraction via trafilatura.

Discovers articles by scraping article links from the HTML listing page
using curl_cffi browser impersonation.  Full article text is always
extracted using trafilatura.
"""

from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import urljoin, urlparse

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

    Scrapes the source URL's HTML listing page for article links, then
    extracts full text from each article using trafilatura.
    """

    def get_poll_interval(self) -> int:
        return self.config.poll_interval or 3600

    # --- Public entry point -----------------------------------------------

    async def fetch(self) -> List[ContentItem]:
        """Fetch blog articles by scraping the HTML listing page."""
        url = self.config.url
        html = await self._fetch_page(url)
        return await self._scrape_html_listing(html, url)

    # --- HTTP helper ------------------------------------------------------

    async def _fetch_page(self, url: str) -> str:
        """Fetch a page using browser impersonation and rate limiting."""
        await get_rate_limiter().acquire(url)
        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.get(url, timeout=30.0)
            response.raise_for_status()
        return response.text

    # --- HTML listing scrape ----------------------------------------------

    async def _scrape_html_listing(self, html: str, base_url: str) -> List[ContentItem]:
        """Scrape article links from an HTML listing page and extract each."""
        article_urls = self._extract_article_urls(html, base_url)
        if not article_urls:
            logger.warning(f"No article links found on {base_url}")
            return []

        new_urls = await self._filter_seen_urls(article_urls)
        skipped = len(article_urls) - len(new_urls)
        if skipped:
            logger.info(f"Skipping {skipped}/{len(article_urls)} already processed articles")
        if not new_urls:
            logger.info(f"No new articles found on {base_url}")
            return []

        logger.info(f"Discovered {len(new_urls)} new article URLs from {base_url}")
        return await self._extract_from_urls(new_urls, origin=base_url)

    # --- Extraction loop --------------------------------------------------

    async def _extract_from_urls(
        self,
        urls: list[str],
        origin: str,
    ) -> List[ContentItem]:
        """Extract content from a list of article URLs."""
        items: list[ContentItem] = []
        extractor = ContentExtractor()

        for article_url in urls:
            content = await extractor.extract_article(
                article_url,
                language=self.config.metadata.get("language"),
                min_length=200,
            )

            if not content:
                logger.debug(f"Could not extract content from {article_url}")
                continue

            item = self._build_item(article_url, content)
            if item:
                items.append(item)

        logger.info(f"Fetched {len(items)} blog articles from {origin}")
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

    # --- Item builder -----------------------------------------------------

    def _build_item(self, url: str, content: str) -> ContentItem | None:
        """Build a ContentItem from extracted content."""
        title = self._title_from_url(url)

        return ContentItem(
            id=f"{self.source_id}:{url}",
            source_id=self.source_id,
            url=url,
            title=title,
            content=content,
            published_at=None,
            metadata={
                "extraction_method": "trafilatura",
                "discovery_method": "html_scrape",
                "is_full_text": True,
            },
        )

    @staticmethod
    def _title_from_url(url: str) -> str:
        """Derive a human-readable title from an article URL slug."""
        path = urlparse(url).path.rstrip("/")
        slug = path.rsplit("/", 1)[-1] if "/" in path else path
        return re.sub(r"[-_]", " ", slug).strip().title() or "Untitled"


# Auto-register on import
AdapterRegistry.register(SourceType.BLOG, BlogAdapter)
