"""Content extraction service using trafilatura for full-text article retrieval."""

from __future__ import annotations

import logging

import trafilatura
from curl_cffi.requests import AsyncSession

from app.infrastructure.rate_limiter import DomainRateLimiter, get_rate_limiter
from app.infrastructure.robots_checker import RobotsChecker

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extract full article text from URLs using trafilatura.

    Respects robots.txt and rate limits between requests.
    """

    def __init__(
        self,
        rate_limiter: DomainRateLimiter | None = None,
        robots_checker: RobotsChecker | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter or get_rate_limiter()
        self._robots_checker = robots_checker or RobotsChecker()

    async def extract_article(
        self,
        url: str,
        language: str | None = None,
        min_length: int = 100,
    ) -> str | None:
        """Extract full article text from URL.

        Args:
            url: Article URL to extract content from.
            language: Optional language code for filtering (e.g., 'en').
            min_length: Minimum content length to consider valid.

        Returns:
            Extracted text or None if extraction failed.
        """
        try:
            # Use browser impersonation for all requests to avoid detection
            async with AsyncSession(impersonate="chrome110") as session:
                # Check robots.txt compliance
                allowed = await self._robots_checker.can_fetch(url, session)
                if not allowed:
                    logger.warning(
                        "robots.txt denies access to %s, skipping extraction",
                        url,
                    )
                    return None

                # Apply rate limiting before fetch
                await self._rate_limiter.acquire(url)

                # Fetch article HTML
                response = await session.get(url, timeout=30.0)
                if response.status_code >= 400:
                    logger.error(
                        "HTTP %d fetching article %s",
                        response.status_code,
                        url,
                    )
                    return None

            # Extract clean text with trafilatura
            extracted = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=False,
                deduplicate=True,
                target_language=language,
                url=url,
            )

            # Validate minimum length
            if extracted and len(extracted) >= min_length:
                return extracted

            if extracted:
                logger.warning(
                    "Extracted content from %s too short (%d < %d chars)",
                    url,
                    len(extracted),
                    min_length,
                )
            else:
                logger.warning("trafilatura returned no content for %s", url)

            return None

        except Exception:
            logger.exception("Failed to extract article from %s", url)
            return None


async def extract_article(url: str, **kwargs: object) -> str | None:
    """Convenience function using a default ContentExtractor."""
    extractor = ContentExtractor()
    return await extractor.extract_article(url, **kwargs)
