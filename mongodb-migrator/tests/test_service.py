from __future__ import annotations

import json
from pathlib import Path

import pytest

from mongodb_migrator.errors import ConfigurationError
from mongodb_migrator.models import MigrationJob
from mongodb_migrator.service import MongoMigrationService


def test_load_job_parses_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "job.yaml"
    config_path.write_text(
        """
source:
  uri: mongodb://src
  database: app
target:
  uri: mongodb://dst
  database: app-copy
selection:
  include_collections:
    - users
execution:
  batch_size: 50
verification:
  enabled: true
  sample_size: 5
""".strip(),
        encoding="utf-8",
    )

    service = MongoMigrationService()
    job = service.load_job(str(config_path))

    assert isinstance(job, MigrationJob)
    assert job.selection.include_collections == ("users",)
    assert job.execution.batch_size == 50


def test_inspect_job_requires_explicit_collection_selection() -> None:
    job = MigrationJob.model_validate(
        {
            "source": {"uri": "mongodb://src", "database": "app"},
            "target": {"uri": "mongodb://dst", "database": "app-copy"},
        }
    )
    service = MongoMigrationService()

    with pytest.raises(ConfigurationError):
        service.inspect_job(job)


def test_inspect_job_renders_json_summary() -> None:
    job = MigrationJob.model_validate(
        {
            "source": {"uri": "mongodb://src", "database": "app"},
            "target": {"uri": "mongodb://dst", "database": "app-copy"},
            "selection": {"include_collections": ["users", "orders"]},
        }
    )
    service = MongoMigrationService()

    rendered = service.inspect_job(job)
    payload = json.loads(rendered)

    assert payload["source_database"] == "app"
    assert [item["source_collection"] for item in payload["collections"]] == ["users", "orders"]
