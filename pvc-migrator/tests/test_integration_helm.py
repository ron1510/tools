from __future__ import annotations

from pathlib import Path

import pytest

from pvc_migrator.models import ChartInput
from pvc_migrator.rendering import HelmRenderer


@pytest.mark.integration
def test_helm_renderer_renders_fixture_chart() -> None:
    chart_dir = Path(__file__).parent / "fixtures" / "charts" / "basic-migrator-app"
    values_file = chart_dir / "values-source.yaml"
    resources = HelmRenderer().render(
        ChartInput(
            chart=str(chart_dir),
            values_file=str(values_file),
            release_name="source-app",
        )
    )
    kinds = {resource["kind"] for resource in resources}
    assert "StatefulSet" in kinds
    assert "Deployment" in kinds
