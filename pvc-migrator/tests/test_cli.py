from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pvc_migrator.cli import main
from pvc_migrator.errors import ExecutionBlockedError
from pvc_migrator.models import ClusterRef, MigrationPlan, WorkloadPlan


class ServiceSpy:
    def __init__(self, plan: MigrationPlan, should_raise: Exception | None = None) -> None:
        self.plan = plan
        self.should_raise = should_raise
        self.executed = False
        self.execute_kwargs: dict[str, Any] = {}

    def build_plan(self, request: Any) -> MigrationPlan:
        del request
        if self.should_raise is not None:
            raise self.should_raise
        return self.plan

    def execute_plan(self, plan: MigrationPlan, **kwargs: Any) -> None:
        del plan
        self.executed = True
        self.execute_kwargs = kwargs


def make_plan() -> MigrationPlan:
    return MigrationPlan(
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        workload_plans=(WorkloadPlan(workload_name="db", category="generic", engine="pv-migrate"),),
        blockers=("x",),
    )


def test_cli_writes_plan_to_output_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_file = tmp_path / "plan.json"
    service = ServiceSpy(
        MigrationPlan(
            source_cluster=ClusterRef(namespace="src"),
            destination_cluster=ClusterRef(namespace="dst"),
            workload_plans=(WorkloadPlan(workload_name="db", category="generic", engine="pv-migrate"),),
        )
    )
    monkeypatch.setattr("pvc_migrator.cli.MigrationPlannerService", lambda: service)
    exit_code = main(
        [
            "plan",
            "--source-chart",
            "source",
            "--dest-chart",
            "dest",
            "--source-namespace",
            "src",
            "--dest-namespace",
            "dst",
            "--output",
            "json",
            "--output-file",
            str(output_file),
        ]
    )
    assert exit_code == 0
    assert json.loads(output_file.read_text(encoding="utf-8"))["source_cluster"]["namespace"] == "src"


def test_cli_execute_invokes_service(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ServiceSpy(
        MigrationPlan(
            source_cluster=ClusterRef(namespace="src"),
            destination_cluster=ClusterRef(namespace="dst"),
            workload_plans=(WorkloadPlan(workload_name="db", category="generic", engine="pv-migrate"),),
        )
    )
    monkeypatch.setattr("pvc_migrator.cli.MigrationPlannerService", lambda: service)
    exit_code = main(
        [
            "execute",
            "--source-chart",
            "source",
            "--dest-chart",
            "dest",
            "--source-namespace",
            "src",
            "--dest-namespace",
            "dst",
            "--approve",
        ]
    )
    assert exit_code == 0
    assert service.executed is True
    assert service.execute_kwargs["approved"] is True


def test_cli_prints_errors(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    service = ServiceSpy(make_plan(), should_raise=ExecutionBlockedError("boom"))
    monkeypatch.setattr("pvc_migrator.cli.MigrationPlannerService", lambda: service)
    exit_code = main(
        [
            "plan",
            "--source-chart",
            "source",
            "--dest-chart",
            "dest",
            "--source-namespace",
            "src",
            "--dest-namespace",
            "dst",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "boom" in captured.err
