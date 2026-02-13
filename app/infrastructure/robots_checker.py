"""robots.txt compliance checking with caching via Protego."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from protego import Protego

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Check robots.txt rules before fetching URLs."""

    def __init__(
        self,
        user_agent: str = "NewsPostBot/1.0",
        cache_ttl: int = 3600,
    ) -> None:
        self.user_agent = user_agent
        self._cache: dict[str, Protego] = {}
        self._cache_times: dict[str, datetime] = {}
        self._cache_ttl = cache_ttl

    def _domain_key(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _is_cache_valid(self, domain: str) -> bool:
        if domain not in self._cache_times:
            return False
        age = (
            datetime.now(timezone.utc) - self._cache_times[domain]
        ).total_seconds()
        return age < self._cache_ttl

    async def _fetch_robots(
        self, domain: str, client: httpx.AsyncClient
    ) -> Protego | None:
        """Fetch and parse robots.txt for a domain."""
        robots_url = f"{domain}/robots.txt"
        try:
            response = await client.get(robots_url, timeout=10.0)
            if response.status_code == 404:
                # No robots.txt means no restrictions
                return Protego.parse("")
            response.raise_for_status()
            return Protego.parse(response.text)
        except Exception:
            logger.warning("Failed to fetch robots.txt from %s", robots_url)
            return None

    async def can_fetch(
        self, url: str, client: httpx.AsyncClient
    ) -> bool:
        """Check if URL is allowed by robots.txt.

        Returns True on any error (fail open).
        """
        try:
            domain = self._domain_key(url)

            if not self._is_cache_valid(domain):
                rp = await self._fetch_robots(domain, client)
                if rp is None:
                    return True  # Fail open
                self._cache[domain] = rp
                self._cache_times[domain] = datetime.now(timezone.utc)

            rp = self._cache[domain]
            allowed = rp.can_fetch(url, self.user_agent)
            if not allowed:
                logger.warning(
                    "robots.txt denies access to %s for %s",
                    url,
                    self.user_agent,
                )
            return allowed
        except Exception:
            logger.exception("Error checking robots.txt for %s", url)
            return True  # Fail open

    async def get_crawl_delay(
        self, url: str, client: httpx.AsyncClient
    ) -> float | None:
        """Get crawl-delay from robots.txt if specified."""
        try:
            domain = self._domain_key(url)
            if not self._is_cache_valid(domain):
                rp = await self._fetch_robots(domain, client)
                if rp is None:
                    return None
                self._cache[domain] = rp
                self._cache_times[domain] = datetime.now(timezone.utc)

            return self._cache[domain].crawl_delay(self.user_agent)
        except Exception:
            return None

    def clear_cache(self) -> None:
        """Clear the robots.txt cache."""
        self._cache.clear()
        self._cache_times.clear()


async def can_fetch(
    url: str, user_agent: str = "NewsPostBot/1.0"
) -> bool:
    """Convenience function using a temporary client."""
    checker = RobotsChecker(user_agent=user_agent)
    async with httpx.AsyncClient() as client:
        return await checker.can_fetch(url, client)
