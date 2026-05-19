from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from pvc_migrator.errors import RenderChartError
from pvc_migrator.models import ChartInput, ValuesSummary, parse_rendered_resources


class HelmRenderer:
    def render(self, chart_input: ChartInput) -> tuple[dict[str, Any], ...]:
        command = ["helm", "template"]
        if chart_input.release_name:
            command.append(chart_input.release_name)
        else:
            command.append("pvc-migrator")
        command.append(chart_input.chart)
        if chart_input.values_file:
            command.extend(["-f", chart_input.values_file])

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise RenderChartError(f"helm template failed: {exc}") from exc

        try:
            documents = list(yaml.safe_load_all(completed.stdout))
        except yaml.YAMLError as exc:
            raise RenderChartError(f"helm template returned invalid YAML: {exc}") from exc
        parsed = parse_rendered_resources([doc for doc in documents if isinstance(doc, dict)])
        return tuple(resource.model_dump(mode="python", exclude_none=True) for resource in parsed)


def load_values_summary(path: str | None) -> ValuesSummary:
    if path is None:
        return ValuesSummary()
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return ValuesSummary()
    plugins_raw = payload.get("plugins")
    if isinstance(plugins_raw, list):
        plugins = tuple(str(item) for item in plugins_raw)
    else:
        plugins = ()
    return ValuesSummary(plugins=plugins)
