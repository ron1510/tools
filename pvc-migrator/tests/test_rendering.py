from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from pvc_migrator.errors import RenderChartError
from pvc_migrator.models import ChartInput
from pvc_migrator.rendering import HelmRenderer, load_values_summary


def test_load_values_summary_reads_plugins(tmp_path: Path) -> None:
    values_file = tmp_path / "values.yaml"
    values_file.write_text("plugins:\n  - grafana-clock-panel\n", encoding="utf-8")
    summary = load_values_summary(str(values_file))
    assert summary.plugins == ("grafana-clock-panel",)


def test_load_values_summary_ignores_non_mapping(tmp_path: Path) -> None:
    values_file = tmp_path / "values.yaml"
    values_file.write_text("- not-a-map\n", encoding="utf-8")
    summary = load_values_summary(str(values_file))
    assert summary.plugins == ()


def test_helm_renderer_reports_subprocess_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.CalledProcessError(returncode=1, cmd="helm template")

    monkeypatch.setattr("pvc_migrator.rendering.subprocess.run", fake_run)
    renderer = HelmRenderer()
    with pytest.raises(RenderChartError, match="helm template failed"):
        renderer.render(ChartInput(chart="chart"))


def test_helm_renderer_reports_invalid_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = subprocess.CompletedProcess(args=["helm"], returncode=0, stdout=":\n", stderr="")
    monkeypatch.setattr("pvc_migrator.rendering.subprocess.run", lambda *args, **kwargs: completed)
    renderer = HelmRenderer()
    with pytest.raises(RenderChartError, match="invalid YAML"):
        renderer.render(ChartInput(chart="chart"))
