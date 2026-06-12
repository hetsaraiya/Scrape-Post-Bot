"""Application configuration via Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    APP_NAME: str = "News Post"
    DEBUG: bool = False
    API_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Blog scraping
    ARTICLE_PATH_PREFIXES: str = "/news/,/blog/,/research/,/posts/,/articles/,/updates/,/announcements/"
    MAX_HTML_ARTICLES: int = 25

    # Pipeline
    PIPELINE_ENABLED: bool = True

    GEMINI_API_KEY: str | None = None

    @field_validator("API_KEY")
    @classmethod
    def api_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("API_KEY must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Used as a FastAPI dependency."""
    return Settings()
