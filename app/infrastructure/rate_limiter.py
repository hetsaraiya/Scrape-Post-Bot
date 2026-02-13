"""Per-domain rate limiting using token bucket algorithm via aiolimiter."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

from aiolimiter import AsyncLimiter

logger = logging.getLogger(__name__)


class DomainRateLimiter:
    """Rate limiter that tracks limits per domain to prevent hammering."""

    def __init__(
        self, default_rate: float = 0.5, default_burst: int = 3
    ) -> None:
        """Initialize rate limiter.

        Args:
            default_rate: Requests per second (0.5 = 1 request per 2 seconds).
            default_burst: Max concurrent requests before throttling.
        """
        self.default_rate = default_rate
        self.default_burst = default_burst
        self._limiters: dict[str, AsyncLimiter] = {}

    def _domain_key(self, url: str) -> str:
        """Extract domain key from URL (scheme + netloc)."""
        try:
            parsed = urlparse(url)
            if parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            logger.warning("Failed to parse URL for rate limiting: %s", url)
        return "__default__"

    def get_limiter(self, url: str) -> AsyncLimiter:
        """Get or create an AsyncLimiter for the URL's domain."""
        key = self._domain_key(url)
        if key not in self._limiters:
            self._limiters[key] = AsyncLimiter(
                max_rate=self.default_burst,
                time_period=self.default_burst / self.default_rate,
            )
            logger.debug("Created rate limiter for domain: %s", key)
        return self._limiters[key]

    async def acquire(self, url: str) -> None:
        """Wait for a rate limit slot for the given URL's domain."""
        limiter = self.get_limiter(url)
        await limiter.acquire()

    async def acquire_with_timeout(
        self, url: str, timeout: float
    ) -> bool:
        """Try to acquire a rate limit slot with a timeout.

        Returns:
            True if slot acquired, False if timed out.
        """
        try:
            await asyncio.wait_for(self.acquire(url), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning(
                "Rate limit timeout for %s after %.1fs", url, timeout
            )
            return False


_default_limiter: DomainRateLimiter | None = None


def get_rate_limiter() -> DomainRateLimiter:
    """Return the singleton DomainRateLimiter instance."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = DomainRateLimiter()
    return _default_limiter
