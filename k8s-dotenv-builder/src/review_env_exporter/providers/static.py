from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import final

from review_env_exporter.constants import ROUTE_KIND, SERVICE_KIND
from review_env_exporter.models import (
    BaseKubernetesResource,
    NormalizedResources,
    RawResource,
    ResourceSelectionConfig,
    parse_kubernetes_resource,
)


@final
class StaticResourceProvider:
    def __init__(
        self, resources: Sequence[RawResource | BaseKubernetesResource]
    ) -> None:
        self._resources = tuple(
            parse_kubernetes_resource(resource) for resource in resources
        )

    @lru_cache(maxsize=32)
    def list_resources(self, config: ResourceSelectionConfig) -> NormalizedResources:
        selected = []
        for resource in self._resources:
            if resource.metadata.namespace not in (None, config.namespace):
                continue
            if resource.kind == ROUTE_KIND and not config.includes(ROUTE_KIND):
                continue
            if resource.kind == SERVICE_KIND and not config.includes(SERVICE_KIND):
                continue
            selected.append(resource)
        return tuple(selected)
