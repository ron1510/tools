from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from pvc_migrator.cli import main
from pvc_migrator.discovery import discover_workloads
from pvc_migrator.models import (
    ChartInput,
    ClusterRef,
    LiveClusterState,
    PersistentVolumeClaimInfo,
    PlanRequest,
    PreflightCheck,
    ValuesSummary,
    parse_rendered_resources,
)
from pvc_migrator.service import MigrationPlannerService
from tests.factories import make_deployment, make_statefulset


class StaticRenderer:
    def __init__(self, source_docs: tuple[dict[str, Any], ...], dest_docs: tuple[dict[str, Any], ...]) -> None:
        self._source_docs = source_docs
        self._dest_docs = dest_docs

    def render(self, chart_input: ChartInput) -> tuple[dict[str, Any], ...]:
        if chart_input.chart == "source":
            return self._source_docs
        return self._dest_docs


class StaticInspector:
    def __init__(
        self,
        source_pvcs: tuple[PersistentVolumeClaimInfo, ...],
        dest_pvcs: tuple[PersistentVolumeClaimInfo, ...],
    ) -> None:
        self._source = LiveClusterState(pvcs=source_pvcs)
        self._dest = LiveClusterState(pvcs=dest_pvcs)

    def list_pvcs(self, cluster: ClusterRef, selector: str | None = None) -> LiveClusterState:
        del selector
        return self._source if cluster.namespace == "source-ns" else self._dest


def no_preflight(**kwargs: Any) -> tuple[PreflightCheck, ...]:
    del kwargs
    return ()


def test_discover_workloads_classifies_vmagent_and_grafana() -> None:
    resources = parse_rendered_resources(
        [
            make_deployment("vmagent"),
            make_deployment("grafana"),
        ]
    )
    workloads = discover_workloads(
        resources,
        ValuesSummary(plugins=("grafana-clock-panel",)),
        ChartInput(chart="x", values_file=None, release_name=None),
    )
    assert [workload.category for workload in workloads] == ["victoriametrics-aux", "grafana"]
    assert workloads[1].plugin_declarations == ("grafana-clock-panel",)


def test_build_plan_uses_pv_migrate_for_generic_statefulset() -> None:
    source_docs = (make_statefulset("src-app-db", "data", replicas=2),)
    dest_docs = (make_statefulset("dst-app-db", "data", replicas=2),)
    source_pvcs = tuple(
        PersistentVolumeClaimInfo(name=f"data-src-app-db-{i}", namespace="source-ns")
        for i in range(2)
    )
    dest_pvcs = tuple(
        PersistentVolumeClaimInfo(name=f"data-dst-app-db-{i}", namespace="dest-ns")
        for i in range(2)
    )
    service = MigrationPlannerService(
        renderer=StaticRenderer(source_docs, dest_docs),
        inspector=StaticInspector(source_pvcs, dest_pvcs),
        preflight_runner=no_preflight,
    )
    plan = service.build_plan(
        PlanRequest(
            source=ChartInput(chart="source"),
            destination=ChartInput(chart="dest"),
            source_cluster=ClusterRef(namespace="source-ns", context="src"),
            destination_cluster=ClusterRef(namespace="dest-ns", context="dst"),
        )
    )
    assert plan.workload_plans[0].engine == "pv-migrate"
    assert len(plan.workload_plans[0].commands) == 2


def test_build_plan_detects_vmstorage_and_blocks_forced_pv_migrate() -> None:
    source_docs = (make_statefulset("vmstorage-src", "data", image="victoriametrics/vmstorage:1"),)
    dest_docs = (make_statefulset("vmstorage-dst", "data", image="victoriametrics/vmstorage:1"),)
    source_pvcs = (PersistentVolumeClaimInfo(name="data-vmstorage-src-0", namespace="source-ns"),)
    dest_pvcs = (PersistentVolumeClaimInfo(name="data-vmstorage-dst-0", namespace="dest-ns"),)
    service = MigrationPlannerService(
        renderer=StaticRenderer(source_docs, dest_docs),
        inspector=StaticInspector(source_pvcs, dest_pvcs),
        preflight_runner=no_preflight,
    )
    plan = service.build_plan(
        PlanRequest(
            source=ChartInput(chart="source"),
            destination=ChartInput(chart="dest"),
            source_cluster=ClusterRef(namespace="source-ns"),
            destination_cluster=ClusterRef(namespace="dest-ns"),
            engine_override="pv-migrate",
        )
    )
    assert plan.workload_plans[0].engine == "victoriametrics-vmstorage"
    assert "refusing to force pv-migrate" in plan.workload_plans[0].blockers[0]


def test_build_plan_prefers_grafana_rehydrate_when_plugins_declared(tmp_path: Path) -> None:
    source_values = tmp_path / "source-values.yaml"
    dest_values = tmp_path / "dest-values.yaml"
    source_values.write_text(yaml.safe_dump({"plugins": ["grafana-clock-panel"]}), encoding="utf-8")
    dest_values.write_text(yaml.safe_dump({"plugins": ["grafana-clock-panel"]}), encoding="utf-8")

    service = MigrationPlannerService(
        renderer=StaticRenderer((make_deployment("grafana"),), (make_deployment("grafana"),)),
        inspector=StaticInspector((), ()),
        preflight_runner=no_preflight,
    )
    plan = service.build_plan(
        PlanRequest(
            source=ChartInput(chart="source", values_file=str(source_values)),
            destination=ChartInput(chart="dest", values_file=str(dest_values)),
            source_cluster=ClusterRef(namespace="source-ns"),
            destination_cluster=ClusterRef(namespace="dest-ns"),
        )
    )
    assert plan.workload_plans[0].engine == "grafana-plugins"
    assert "helm upgrade" in plan.workload_plans[0].commands[0].command


def test_cli_plan_outputs_json(monkeypatch: Any, capsys: Any) -> None:
    service = MigrationPlannerService(
        renderer=StaticRenderer((make_statefulset("src-app-db", "data"),), (make_statefulset("dst-app-db", "data"),)),
        inspector=StaticInspector(
            (PersistentVolumeClaimInfo(name="data-src-app-db-0", namespace="source-ns"),),
            (PersistentVolumeClaimInfo(name="data-dst-app-db-0", namespace="dest-ns"),),
        ),
        preflight_runner=no_preflight,
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
            "source-ns",
            "--dest-namespace",
            "dest-ns",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["workload_plans"][0]["engine"] == "pv-migrate"
