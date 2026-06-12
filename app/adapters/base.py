"""Abstract base class for all source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.models.content_item import ContentItem
from app.models.source_config import SourceConfig


class SourceAdapter(ABC):
    """Abstract base class for all source adapters."""

    def __init__(self, source_config: SourceConfig) -> None:
        self.config = source_config
        self.source_id = source_config.id

    @abstractmethod
    async def fetch(self) -> List[ContentItem]:
        """Fetch new content items from source.

        Returns list of ContentItem objects.
        Should handle rate limiting internally.
        """
        pass

    @abstractmethod
    def get_poll_interval(self) -> int:
        """Return poll interval in seconds."""
        pass
