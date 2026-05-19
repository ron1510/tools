from __future__ import annotations

import logging
from typing import final

from review_env_exporter.constants import EXPORT_LABEL
from review_env_exporter.exporter import collect_env_entries, render_dotenv
from review_env_exporter.models import ResourceSelectionConfig
from review_env_exporter.providers.base import ResourceProvider


@final
class ReviewEnvExporterService:
    def __init__(
        self,
        provider: ResourceProvider,
        config: ResourceSelectionConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self._provider = provider
        self._config = config
        self._logger = logger or logging.getLogger(__name__)

    def generate_env(self) -> str:
        self._logger.info(
            "Fetching cluster resources", extra={"namespace": self._config.namespace}
        )
        resources = self._provider.list_resources(self._config)
        exportable_resources = sum(
            1
            for resource in resources
            if resource.metadata.labels.get(EXPORT_LABEL) == "true"
        )
        ignored_resources = len(resources) - exportable_resources
        self._logger.info(
            "Fetched cluster resources",
            extra={
                "count": len(resources),
                "exportable": exportable_resources,
                "ignored": ignored_resources,
            },
        )
        entries = collect_env_entries(resources)
        self._logger.info("Generated env entries", extra={"entries": len(entries)})
        return render_dotenv(entries)
