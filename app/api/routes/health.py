"""Health check endpoint."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from starlette.responses import JSONResponse

from app.api.deps import get_current_api_key
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    redis: str


@router.get(
    "",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def health_check(
    redis: Redis = Depends(get_redis),
    _api_key: str = Depends(get_current_api_key),
) -> JSONResponse:
    """Check application and Redis health."""
    try:
        await redis.ping()
        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "redis": "connected"},
        )
    except Exception:
        logger.exception("Health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "redis": "disconnected"},
        )
