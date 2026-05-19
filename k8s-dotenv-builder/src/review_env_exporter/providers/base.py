from __future__ import annotations

from typing import Protocol

from review_env_exporter.models import NormalizedResources, ResourceSelectionConfig


class ResourceProvider(Protocol):
    def list_resources(
        self, config: ResourceSelectionConfig
    ) -> NormalizedResources: ...
