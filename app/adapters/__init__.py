"""Source adapters for content fetching."""

from app.adapters.base import SourceAdapter
from app.adapters.registry import AdapterRegistry

# Import concrete adapters to trigger their module-level self-registration
from app.adapters import rss_adapter as _rss_adapter  # noqa: F401
from app.adapters import blog_adapter as _blog_adapter  # noqa: F401

__all__ = ["SourceAdapter", "AdapterRegistry"]
