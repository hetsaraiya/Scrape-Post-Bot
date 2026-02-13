"""API key authentication."""

import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """Validate the API key from request header."""
    if api_key is None:
        raise HTTPException(status_code=401, detail="API key required")
    if not secrets.compare_digest(api_key, get_settings().API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
