"""Source management REST API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

import orjson
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.adapters.registry import AdapterRegistry
from app.api.deps import get_current_api_key
from app.core.redis import get_redis
from app.models.source_config import SourceConfig, SourceType
from app.scheduler.jobs import SourceScheduler, poll_source_job
from app.scheduler.scheduler import get_source_scheduler
from app.services.baseline import perform_baseline_scrape

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
    return SourceResponse(
        id=config.id,
        name=config.name,
        url=config.url,
        type=config.type,
        poll_interval=config.poll_interval,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
        last_poll_at=config.last_poll_at,
        error_count=config.error_count,
        last_error=config.last_error,
    )


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
    supported = AdapterRegistry.get_supported_types()
    if body.type not in supported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported source type: {body.type}. Supported: {supported}",
        )

    now = datetime.now(timezone.utc)
    source_id = str(uuid.uuid4())

    config = SourceConfig(
        id=source_id,
        name=body.name,
        url=str(body.url),
        type=body.type,
        poll_interval=body.poll_interval,
        is_active=True,
        created_at=now,
        updated_at=now,
        last_poll_at=None,
        last_error=None,
        error_count=0,
        rate_limit=None,
        metadata=body.metadata,
        baseline_complete=False,
    )

    await redis.set(_redis_key(source_id), config.to_redis())

    # Run baseline scrape in background — marks existing content as seen
    # so polls only queue items published after this moment
    background_tasks.add_task(perform_baseline_scrape, config, redis)

    try:
        scheduler: SourceScheduler = get_source_scheduler()
        if config.is_active:
            scheduler.add_source(config)
    except RuntimeError:
        pass  # Scheduler not running (e.g. tests)

    return _to_response(config)


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> List[SourceResponse]:
    """List all monitored sources."""
    keys = await redis.keys(f"{_REDIS_KEY_PREFIX}*")
    sources = []
    for key in keys:
        raw = await redis.get(key)
        if raw is not None:
            try:
                sources.append(_to_response(SourceConfig.from_redis(raw)))
            except Exception:
                pass  # Skip corrupted entries
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

    try:
        scheduler: SourceScheduler = get_source_scheduler()
        if was_active and config.is_active:
            scheduler.update_source(config)
        elif not was_active and config.is_active:
            scheduler.add_source(config)
        elif was_active and not config.is_active:
            scheduler.remove_source(source_id)
    except RuntimeError:
        pass  # Scheduler not running (e.g. tests)

    return _to_response(config)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> None:
    """Remove a monitored source."""
    await _get_source_or_404(source_id, redis)

    try:
        scheduler: SourceScheduler = get_source_scheduler()
        scheduler.remove_source(source_id)
    except RuntimeError:
        pass  # Scheduler not running (e.g. tests)

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
