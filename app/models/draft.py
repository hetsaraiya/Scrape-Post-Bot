"""Draft model for generated LinkedIn posts with Redis serialization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

import orjson
from pydantic import BaseModel, Field


class Draft(BaseModel):
    """A generated LinkedIn draft post ready for review."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content_item_id: str
    source_id: str
    title: str
    body: str = Field(..., description="The LinkedIn post text")
    original_url: str
    evaluation_score: float
    evaluation_reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["pending", "approved", "rejected", "published"] = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

    def to_redis(self) -> str:
        """Serialize to JSON string for Redis storage."""
        return orjson.dumps(
            self.model_dump(mode="json"),
        ).decode("utf-8")

    @classmethod
    def from_redis(cls, data: str | bytes) -> Draft:
        """Deserialize from Redis JSON string."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.model_validate(orjson.loads(data))
