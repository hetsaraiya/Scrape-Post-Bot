"""FastAPI application with lifespan manager."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.v1.drafts import router as drafts_router
from app.api.v1.sources import router as sources_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.redis import close_redis, get_redis, init_redis
from app.middleware.correlation import CorrelationIdMiddleware
from app.pipeline.worker import start_pipeline_worker, stop_pipeline_worker
from app.scheduler.scheduler import init_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown."""
    settings = get_settings()

    setup_logging(settings.LOG_LEVEL)
    logger = get_logger(__name__)
    logger.info(f"Starting {settings.APP_NAME}")

    await init_redis(settings.REDIS_URL)
    await init_scheduler(get_redis())

    if settings.PIPELINE_ENABLED:
        await start_pipeline_worker(get_redis())

    yield

    await stop_pipeline_worker()
    await shutdown_scheduler()
    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title="News Post",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health_router)
app.include_router(sources_router, prefix="/api/v1")
app.include_router(drafts_router, prefix="/api/v1")
