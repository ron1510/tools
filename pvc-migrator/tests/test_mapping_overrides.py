from __future__ import annotations

from pathlib import Path

import pytest

from pvc_migrator.mapping_overrides import load_mapping_overrides


def test_load_mapping_overrides_reads_workloads_and_pvcs(tmp_path: Path) -> None:
    mapping_file = tmp_path / "mapping.yaml"
    mapping_file.write_text(
        "workloads:\n"
        "  - source_workload: src-db\n"
        "    destination_workload: dst-db\n"
        "pvcs:\n"
        "  - source_pvc: data-src-db-0\n"
        "    destination_pvc: data-dst-db-0\n",
        encoding="utf-8",
    )
    overrides = load_mapping_overrides(str(mapping_file))
    assert overrides.workloads[0].source_workload == "src-db"
    assert overrides.pvcs[0].destination_pvc == "data-dst-db-0"


def test_load_mapping_overrides_rejects_non_mapping(tmp_path: Path) -> None:
    mapping_file = tmp_path / "mapping.yaml"
    mapping_file.write_text("- nope\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top level"):
        load_mapping_overrides(str(mapping_file))
