from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from pvc_migrator.discovery import (
    ClusterInspector,
    build_expected_pvc_names,
    classify_workload,
    discover_workloads,
)
from pvc_migrator.errors import ClusterInspectionError
from pvc_migrator.models import ChartInput, RenderedResource, ValuesSummary, parse_rendered_resources
from tests.factories import make_deployment, make_statefulset, make_vmcluster


def test_build_expected_pvc_names_uses_templates_and_ordinals() -> None:
    names = build_expected_pvc_names("db", 2, ("data", "wal"))
    assert names == ("data-db-0", "data-db-1", "wal-db-0", "wal-db-1")


def test_classify_workload_detects_vmcluster() -> None:
    resource = RenderedResource.model_validate(make_vmcluster("victoria"))
    assert classify_workload(resource) == "victoriametrics-vmstorage"


def test_discover_workloads_adds_grafana_values_only_fallback() -> None:
    workloads = discover_workloads(
        (),
        ValuesSummary(plugins=("plugin-a",)),
        ChartInput(chart="chart", release_name="grafana-release"),
    )
    assert workloads[0].name == "grafana-release"
    assert workloads[0].plugin_declarations == ("plugin-a",)


def test_discover_workloads_extracts_claim_templates() -> None:
    resources = parse_rendered_resources([make_statefulset("db", "data", replicas=2)])
    workloads = discover_workloads(resources, ValuesSummary(), ChartInput(chart="chart"))
    assert workloads[0].expected_pvc_names == ("data-db-0", "data-db-1")


def test_cluster_inspector_parses_kubectl_json(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "items": [
            {
                "metadata": {"name": "data-app-0", "namespace": "src", "labels": {"app": "x"}},
                "spec": {"storageClassName": "fast", "accessModes": ["ReadWriteOnce"]},
            }
        ]
    }
    completed = subprocess.CompletedProcess(args=["kubectl"], returncode=0, stdout=json.dumps(payload), stderr="")
    monkeypatch.setattr("pvc_migrator.discovery.subprocess.run", lambda *args, **kwargs: completed)
    state = ClusterInspector().list_pvcs(cluster=type("Cluster", (), {"namespace": "src", "context": None})())
    assert state.pvcs[0].name == "data-app-0"


def test_cluster_inspector_wraps_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = subprocess.CompletedProcess(args=["kubectl"], returncode=0, stdout="{", stderr="")
    monkeypatch.setattr("pvc_migrator.discovery.subprocess.run", lambda *args, **kwargs: completed)
    with pytest.raises(ClusterInspectionError, match="invalid JSON"):
        ClusterInspector().list_pvcs(cluster=type("Cluster", (), {"namespace": "src", "context": None})())
