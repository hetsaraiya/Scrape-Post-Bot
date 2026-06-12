"""Source management REST API endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.api.deps import get_current_api_key
from app.core.redis import get_redis
from app.models.source_config import SourceConfig, SourceType
from app.scheduler.jobs import SourceScheduler, poll_source_job
from app.scheduler.scheduler import get_source_scheduler
from app.services.baseline import perform_baseline_scrape

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])

_REDIS_KEY_PREFIX = "source:"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str
    type: SourceType
    poll_interval: int = Field(900, ge=60, le=86400)
    metadata: dict = Field(default_factory=dict)


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    poll_interval: int | None = Field(None, ge=30, le=86400)
    is_active: bool | None = None
    metadata: dict | None = None


class SourceResponse(BaseModel):
    id: str
    name: str
    url: str
    type: SourceType
    poll_interval: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_poll_at: datetime | None
    error_count: int
    last_error: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redis_key(source_id: str) -> str:
    return f"{_REDIS_KEY_PREFIX}{source_id}"


async def _get_source_or_404(source_id: str, redis: Redis) -> SourceConfig:
    raw = await redis.get(_redis_key(source_id))
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return SourceConfig.from_redis(raw)


def _to_response(config: SourceConfig) -> SourceResponse:
    return SourceResponse.model_validate(config.model_dump())


def _with_scheduler(action: Callable[[SourceScheduler], None]) -> None:
    """Run an action against the scheduler, skipping if it isn't running (e.g. tests)."""
    try:
        scheduler = get_source_scheduler()
    except RuntimeError:
        return
    action(scheduler)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    background_tasks: BackgroundTasks,
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> SourceResponse:
    """Create a new monitored source.

    Immediately returns 201 and runs an initial baseline scrape in the
    background — marking all current content as already-seen so the first
    real poll only surfaces genuinely new items.
    """
    config = SourceConfig(
        id=str(uuid.uuid4()),
        name=body.name,
        url=str(body.url),
        type=body.type,
        poll_interval=body.poll_interval,
        metadata=body.metadata,
    )

    await redis.set(_redis_key(config.id), config.to_redis())

    # Run baseline scrape in background — marks existing content as seen
    # so polls only queue items published after this moment
    background_tasks.add_task(perform_baseline_scrape, config, redis)

    _with_scheduler(lambda s: s.add_source(config))

    return _to_response(config)


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> List[SourceResponse]:
    """List all monitored sources."""
    sources = []
    async for key in redis.scan_iter(match=f"{_REDIS_KEY_PREFIX}*"):
        raw = await redis.get(key)
        if raw is None:
            continue
        try:
            sources.append(_to_response(SourceConfig.from_redis(raw)))
        except Exception:
            logger.warning(f"Skipping corrupted source entry at {key}", exc_info=True)
    return sources


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> SourceResponse:
    """Get a single monitored source."""
    config = await _get_source_or_404(source_id, redis)
    return _to_response(config)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    body: SourceUpdate,
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> SourceResponse:
    """Update a monitored source."""
    config = await _get_source_or_404(source_id, redis)
    was_active = config.is_active

    if body.name is not None:
        config.name = body.name
    if body.url is not None:
        config.url = str(body.url)
    if body.poll_interval is not None:
        config.poll_interval = body.poll_interval
    if body.is_active is not None:
        config.is_active = body.is_active
    if body.metadata is not None:
        config.metadata = {**config.metadata, **body.metadata}
    config.updated_at = datetime.now(timezone.utc)

    await redis.set(_redis_key(source_id), config.to_redis())

    def sync_schedule(scheduler: SourceScheduler) -> None:
        if was_active and config.is_active:
            scheduler.update_source(config)
        elif not was_active and config.is_active:
            scheduler.add_source(config)
        elif was_active and not config.is_active:
            scheduler.remove_source(source_id)

    _with_scheduler(sync_schedule)

    return _to_response(config)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> None:
    """Remove a monitored source."""
    await _get_source_or_404(source_id, redis)
    _with_scheduler(lambda s: s.remove_source(source_id))
    await redis.delete(_redis_key(source_id))


@router.post("/{source_id}/poll", status_code=status.HTTP_202_ACCEPTED)
async def trigger_poll(
    source_id: str,
    background_tasks: BackgroundTasks,
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> dict:
    """Trigger an immediate manual poll for a source."""
    config = await _get_source_or_404(source_id, redis)
    background_tasks.add_task(poll_source_job, config)
    return {"message": f"Poll triggered for source {source_id}"}
