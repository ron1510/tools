from __future__ import annotations

import json
from pathlib import Path

import yaml

from mongodb_migrator.copy_service import MongoCopyService
from mongodb_migrator.errors import ConfigurationError
from mongodb_migrator.models import (
    CollectionPlan,
    CopyRequest,
    ExecutionOptions,
    MigrationJob,
    SelectionOptions,
)


class MongoMigrationService:
    def __init__(self, copy_service: MongoCopyService | None = None) -> None:
        self._copy_service = copy_service or MongoCopyService()

    def run_copy(self, request: CopyRequest) -> str:
        report = self._copy_service.copy(request)
        lines = []
        for result in report.results:
            status = "skipped" if result.skipped else "copied"
            lines.append(
                f"{result.target_collection}: {status} {result.copied_documents} document(s), "
                f"{result.recreated_indexes} recreated index(es)"
            )
        if report.verification is not None:
            lines.append(
                f"verification: {'passed' if report.verification.success else 'failed'}"
            )
        return "\n".join(lines) + ("\n" if lines else "")

    def inspect_job(self, job: MigrationJob) -> str:
        plans = self._build_plans(job)
        payload = {
            "source_database": job.source.database,
            "target_database": job.target.database,
            "collections": [plan.model_dump(mode="python") for plan in plans],
            "replace_target": job.execution.replace_target,
            "dry_run": job.execution.dry_run,
        }
        return json.dumps(payload, indent=2) + "\n"

    def run_job(self, job: MigrationJob) -> str:
        request = CopyRequest(
            source=job.source,
            target=job.target,
            include_collections=job.selection.include_collections,
            exclude_collections=job.selection.exclude_collections,
            execution=job.execution,
            verification=job.verification,
        )
        return self.run_copy(request)

    def load_job(self, path: str) -> MigrationJob:
        target = Path(path)
        if not target.exists():
            raise ConfigurationError(f"config file does not exist: {target}")
        payload = yaml.safe_load(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ConfigurationError("config file must contain a mapping at the top level")
        normalized = dict(payload)
        if "selection" not in normalized:
            normalized["selection"] = SelectionOptions().model_dump(mode="python")
        if "execution" not in normalized:
            normalized["execution"] = ExecutionOptions().model_dump(mode="python")
        if "collections" in normalized and isinstance(normalized["collections"], list):
            normalized["collections"] = tuple(normalized["collections"])
        return MigrationJob.model_validate(normalized)

    def _build_plans(self, job: MigrationJob) -> tuple[CollectionPlan, ...]:
        if job.collections:
            return job.collections
        include_collections = job.selection.include_collections
        if not include_collections:
            raise ConfigurationError(
                "inspect requires explicit selection.include_collections when collections are not listed"
            )
        return tuple(
            CollectionPlan(source_collection=name, target_collection=name)
            for name in include_collections
        )
