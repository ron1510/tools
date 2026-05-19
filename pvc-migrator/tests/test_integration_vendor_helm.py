from __future__ import annotations

from pathlib import Path

import pytest

from pvc_migrator.discovery import discover_workloads
from pvc_migrator.models import ChartInput, ValuesSummary, parse_rendered_resources
from pvc_migrator.rendering import HelmRenderer


@pytest.mark.integration
def test_vendor_chart_renders_real_vendor_workloads() -> None:
    chart_dir = Path(__file__).parent / "fixtures" / "charts" / "vendor-migrator-app"
    rendered = HelmRenderer().render(
        ChartInput(
            chart=str(chart_dir),
            values_file=str(chart_dir / "values-source.yaml"),
            release_name="vendor-source",
        )
    )
    workloads = discover_workloads(
        parse_rendered_resources(list(rendered)),
        ValuesSummary(),
        ChartInput(chart=str(chart_dir)),
    )
    categories = {workload.category for workload in workloads}
    assert "arangodb-single" in categories
    assert "victoriametrics-vmstorage" in categories
    assert "victoriametrics-aux" in categories
