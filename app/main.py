"""FastAPI application with lifespan manager."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.health import router as health_router
from app.api.v1.drafts import router as drafts_router
from app.api.v1.pipeline import router as pipeline_router
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


tags_metadata = [
    {"name": "health", "description": "Application and Redis health checks"},
    {
        "name": "sources",
        "description": "Manage monitored content sources. CRUD operations and manual polling.",
    },
    {"name": "drafts", "description": "View generated LinkedIn draft posts."},
    {
        "name": "pipeline",
        "description": "Pipeline status, metrics, and manual run triggers.",
    },
]

app = FastAPI(
    title="News Post",
    description=(
        "AI news monitoring and LinkedIn post generation pipeline. "
        "Watches curated AI industry sources, evaluates newsworthiness, "
        "deduplicates across sources, and drafts LinkedIn-ready posts."
    ),
    version="0.1.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)
app.include_router(health_router)
app.include_router(sources_router, prefix="/api/v1")
app.include_router(drafts_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")


class SPAStaticFiles(StaticFiles):
    """Serve the built frontend, falling back to index.html for client-side routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# In the Docker image the built frontend lives in ./static; absent in local dev.
_static_dir = Path(os.getenv("STATIC_DIR", "static"))
if _static_dir.is_dir():
    app.mount("/", SPAStaticFiles(directory=_static_dir, html=True), name="frontend")
