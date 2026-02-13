"""Common API dependencies."""

from app.core.security import verify_api_key

get_current_api_key = verify_api_key
