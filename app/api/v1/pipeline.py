"""Pipeline status, metrics, and manual run API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from pydantic import BaseModel
from redis.asyncio import Redis

from app.api.deps import get_current_api_key
from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.source_config import SourceConfig
from app.pipeline.worker import _worker_task
from app.scheduler.jobs import poll_source_job
from app.services.content_queue import ContentQueue
from app.services.metrics import MetricsService, get_metrics_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class PipelineStatus(BaseModel):
    """Current state of the pipeline worker and queue."""

    worker_running: bool
    queue_depth: int
    active_sources: int
    pipeline_enabled: bool
    worker_state: str
    last_heartbeat: str | None


class PipelineMetricsResponse(BaseModel):
    """Snapshot of pipeline processing counters."""

    items_processed: int
    dedup_hits: int
    eval_passed: int
    eval_failed: int
    gen_success: int
    gen_errors: int


class PipelineRunResponse(BaseModel):
    """Result of a manual pipeline run trigger."""

    message: str
    sources_triggered: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=PipelineStatus)
async def get_pipeline_status(
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> PipelineStatus:
    """Get current pipeline status: worker state, queue depth, active sources."""
    # Worker running check
    worker_running = _worker_task is not None and not _worker_task.done()

    # Queue depth
    queue = ContentQueue(redis)
    queue_depth = await queue.length()

    # Count active sources
    keys = await redis.keys("source:*")
    active_sources = 0
    for key in keys:
        raw = await redis.get(key)
        if raw is not None:
            try:
                config = SourceConfig.from_redis(raw)
                if config.is_active:
                    active_sources += 1
            except Exception:
                pass  # Skip corrupted entries

    # Pipeline enabled setting
    pipeline_enabled = get_settings().PIPELINE_ENABLED

    # Worker state from Redis hash
    status_data: dict[str, str] = await redis.hgetall("pipeline:status")
    worker_state = status_data.get("state", "unknown")
    last_heartbeat = status_data.get("last_heartbeat", None)

    # Redis returns bytes — decode if necessary
    if isinstance(worker_state, bytes):
        worker_state = worker_state.decode("utf-8")
    if isinstance(last_heartbeat, bytes):
        last_heartbeat = last_heartbeat.decode("utf-8")

    return PipelineStatus(
        worker_running=worker_running,
        queue_depth=queue_depth,
        active_sources=active_sources,
        pipeline_enabled=pipeline_enabled,
        worker_state=worker_state,
        last_heartbeat=last_heartbeat,
    )


@router.get("/metrics", response_model=PipelineMetricsResponse)
async def get_pipeline_metrics(
    metrics: MetricsService = Depends(get_metrics_service),
    _api_key: str = Depends(get_current_api_key),
) -> PipelineMetricsResponse:
    """Get pipeline processing metrics: items processed, eval pass rate, dedup hits."""
    data = await metrics.get_all()
    return PipelineMetricsResponse(
        items_processed=data.items_processed,
        dedup_hits=data.dedup_hits,
        eval_passed=data.eval_passed,
        eval_failed=data.eval_failed,
        gen_success=data.gen_success,
        gen_errors=data.gen_errors,
    )


@router.post(
    "/run",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_pipeline_run(
    background_tasks: BackgroundTasks,
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> PipelineRunResponse:
    """Trigger a manual pipeline run for all active, baseline-complete sources."""
    keys = await redis.keys("source:*")
    triggered = 0

    for key in keys:
        raw = await redis.get(key)
        if raw is None:
            continue
        try:
            config = SourceConfig.from_redis(raw)
            if config.is_active and config.baseline_complete:
                background_tasks.add_task(poll_source_job, config)
                triggered += 1
        except Exception:
            pass  # Skip corrupted entries

    return PipelineRunResponse(
        message=f"Pipeline run triggered for {triggered} source(s)",
        sources_triggered=triggered,
    )


@router.post("/metrics/reset", status_code=status.HTTP_200_OK)
async def reset_pipeline_metrics(
    metrics: MetricsService = Depends(get_metrics_service),
    _api_key: str = Depends(get_current_api_key),
) -> dict:
    """Reset all pipeline metrics counters to zero."""
    await metrics.reset()
    return {"message": "Pipeline metrics reset"}
