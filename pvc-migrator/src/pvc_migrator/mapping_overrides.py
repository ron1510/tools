from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pvc_migrator.models import MappingOverrides


def load_mapping_overrides(path: str | None) -> MappingOverrides:
    if path is None:
        return MappingOverrides()
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if payload is None:
        return MappingOverrides()
    if not isinstance(payload, dict):
        raise ValueError("mapping file must contain a mapping/object at the top level")
    normalized: dict[str, Any] = {
        "workloads": payload.get("workloads", ()),
        "pvcs": payload.get("pvcs", ()),
    }
    return MappingOverrides.model_validate(normalized)
