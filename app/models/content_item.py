"""ContentItem model for ingested content with Redis serialization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import orjson
from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """A single content item fetched from a monitored source."""

    id: str = Field(..., description="Unique ID in format '{source_id}:{item_id}'")
    source_id: str
    url: str
    title: str
    content: str = Field(default="", description="Full text content")
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: Optional[str] = Field(
        default=None, description="SHA-256 hash for deduplication"
    )

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    def to_redis(self) -> str:
        """Serialize to JSON string for Redis storage."""
        return orjson.dumps(
            self.model_dump(mode="json"),
        ).decode("utf-8")

    @classmethod
    def from_redis(cls, data: str | bytes) -> ContentItem:
        """Deserialize from Redis JSON string."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.model_validate(orjson.loads(data))
