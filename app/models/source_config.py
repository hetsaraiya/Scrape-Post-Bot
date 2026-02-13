"""SourceConfig model for monitored source metadata."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import orjson
from pydantic import BaseModel, Field


class SourceType(str, enum.Enum):
    """Supported source types."""

    RSS = "rss"
    BLOG = "blog"


class SourceConfig(BaseModel):
    """Configuration for a monitored content source."""

    id: str = Field(..., description="UUID or slug identifier")
    name: str = Field(..., description="Display name")
    url: str = Field(..., description="Source URL")
    type: SourceType
    poll_interval: int = Field(
        default=900, description="Polling interval in seconds (default 15min)"
    )
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_poll_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Adapter-specific config (language, selectors, etc.)",
    )
    rate_limit: Optional[float] = Field(
        default=0.5, description="Max requests per second (default 1 per 2s)"
    )
    baseline_complete: bool = Field(
        default=False,
        description="True after initial baseline scrape has run for this source",
    )

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    @property
    def domain(self) -> str:
        """Extract domain from the source URL."""
        return urlparse(self.url).netloc

    def to_redis(self) -> str:
        """Serialize to JSON string for Redis storage."""
        return orjson.dumps(
            self.model_dump(mode="json"),
        ).decode("utf-8")

    @classmethod
    def from_redis(cls, data: str | bytes) -> SourceConfig:
        """Deserialize from Redis JSON string."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.model_validate(orjson.loads(data))
