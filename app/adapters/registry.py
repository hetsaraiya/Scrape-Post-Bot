"""Factory registry for source adapters."""

from __future__ import annotations

from typing import Dict, Type

from app.adapters.base import SourceAdapter
from app.models.source_config import SourceConfig, SourceType


class AdapterRegistry:
    """Factory registry for source adapters."""

    _adapters: Dict[SourceType, Type[SourceAdapter]] = {}

    @classmethod
    def register(cls, source_type: SourceType, adapter_class: Type[SourceAdapter]) -> None:
        """Register an adapter class for a source type."""
        cls._adapters[source_type] = adapter_class

    @classmethod
    def create(cls, source_config: SourceConfig) -> SourceAdapter:
        """Create adapter instance from source config."""
        if source_config.type not in cls._adapters:
            raise ValueError(f"Unknown source type: {source_config.type}")
        return cls._adapters[source_config.type](source_config)
