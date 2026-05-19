from __future__ import annotations

from pvc_migrator.engines import build_workload_plan
from pvc_migrator.models import ChartInput, ClusterRef, PlanRequest, PvcPair, WorkloadInfo


def make_request(**overrides: object) -> PlanRequest:
    payload = {
        "source": ChartInput(chart="source"),
        "destination": ChartInput(chart="dest"),
        "source_cluster": ClusterRef(namespace="src", context="c1"),
        "destination_cluster": ClusterRef(namespace="dst", context="c2"),
    }
    payload.update(overrides)
    return PlanRequest(**payload)


def make_workload(name: str, category: str, **overrides: object) -> WorkloadInfo:
    payload = {
        "name": name,
        "kind": "StatefulSet",
        "category": category,
    }
    payload.update(overrides)
    return WorkloadInfo(**payload)


def test_generic_engine_builds_pv_migrate_commands() -> None:
    plan = build_workload_plan(
        make_request(),
        ClusterRef(namespace="src", context="c1"),
        ClusterRef(namespace="dst", context="c2"),
        make_workload("app-db", "generic"),
        make_workload("app-db", "generic"),
        (PvcPair(source_name="a", destination_name="b", source_namespace="src", destination_namespace="dst"),),
    )
    assert plan.engine == "pv-migrate"
    assert "--source-context c1" in plan.commands[0].command


def test_aux_engine_stays_skip_without_opt_in() -> None:
    plan = build_workload_plan(
        make_request(),
        ClusterRef(namespace="src"),
        ClusterRef(namespace="dst"),
        make_workload("vmagent", "victoriametrics-aux"),
        make_workload("vmagent", "victoriametrics-aux"),
        (PvcPair(source_name="a", destination_name="b", source_namespace="src", destination_namespace="dst"),),
    )
    assert plan.engine == "victoriametrics-aux-skip"
    assert plan.commands == ()


def test_aux_engine_can_downgrade_to_pv_copy_when_enabled() -> None:
    plan = build_workload_plan(
        make_request(allow_aux_pvc_copy=True),
        ClusterRef(namespace="src"),
        ClusterRef(namespace="dst"),
        make_workload("vmalert", "victoriametrics-aux"),
        make_workload("vmalert", "victoriametrics-aux"),
        (PvcPair(source_name="a", destination_name="b", source_namespace="src", destination_namespace="dst"),),
    )
    assert plan.engine == "pv-migrate"
    assert plan.commands


def test_arangodb_engine_generates_native_commands() -> None:
    plan = build_workload_plan(
        make_request(),
        ClusterRef(namespace="src"),
        ClusterRef(namespace="dst"),
        make_workload("arangodb", "arangodb-single"),
        make_workload("arangodb", "arangodb-single"),
        (),
    )
    assert "arangodump" in plan.commands[0].command


def test_grafana_engine_prefers_redeploy_for_declared_plugins() -> None:
    plan = build_workload_plan(
        make_request(),
        ClusterRef(namespace="src"),
        ClusterRef(namespace="dst"),
        make_workload("grafana", "grafana", plugin_declarations=("plugin-a",)),
        make_workload("grafana", "grafana"),
        (),
    )
    assert plan.engine == "grafana-plugins"
    assert "helm upgrade" in plan.commands[0].command
