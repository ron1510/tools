from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from review_env_exporter.cli import main
from review_env_exporter.errors import FetchResourcesError


@dataclass
class ProviderSpy:
    should_raise: Exception | None = None
    calls: list[Any] = field(default_factory=list)

    def list_resources(self, config: Any) -> tuple[Any, ...]:
        self.calls.append(config)
        if self.should_raise is not None:
            raise self.should_raise
        return tuple()


def test_cli_writes_output_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "review.env"
    rendered = "API_URL=https://example.test\n"

    provider_spy = ProviderSpy()

    def fake_generate_env(self: object) -> str:
        return rendered

    monkeypatch.setattr(
        "review_env_exporter.cli.KubernetesApiResourceProvider",
        lambda access_config: provider_spy,
    )
    monkeypatch.setattr(
        "review_env_exporter.cli.ReviewEnvExporterService.generate_env",
        fake_generate_env,
    )

    exit_code = main(
        ["--namespace", "review", "--output", str(output_path), "--log-level", "ERROR"]
    )

    assert exit_code == 0
    assert output_path.read_text(encoding="utf-8") == rendered


def test_cli_prints_error_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    provider_spy = ProviderSpy(should_raise=FetchResourcesError("boom"))

    monkeypatch.setattr(
        "review_env_exporter.cli.KubernetesApiResourceProvider",
        lambda access_config: provider_spy,
    )

    exit_code = main(["--namespace", "review", "--log-level", "ERROR"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "boom" in captured.err


def test_cli_passes_helm_release_into_selection_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "review.env"
    provider_spy = ProviderSpy()

    captured_selection_config: dict[str, Any] = {}

    def fake_generate_env(self: Any) -> str:
        captured_selection_config["config"] = self._config
        return "API_URL=https://example.test\n"

    monkeypatch.setattr(
        "review_env_exporter.cli.KubernetesApiResourceProvider",
        lambda access_config: provider_spy,
    )
    monkeypatch.setattr(
        "review_env_exporter.cli.ReviewEnvExporterService.generate_env",
        fake_generate_env,
    )

    exit_code = main(
        [
            "--namespace",
            "review",
            "--helm-release",
            "feature-123",
            "--output",
            str(output_path),
            "--log-level",
            "ERROR",
        ]
    )

    assert exit_code == 0
    assert captured_selection_config["config"].helm_release_name == "feature-123"
