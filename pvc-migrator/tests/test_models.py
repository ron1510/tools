from __future__ import annotations

import pytest

from pvc_migrator.models import ChartInput, ClusterRef, MigrationPlan, PlanRequest


def test_cluster_ref_rejects_empty_namespace() -> None:
    with pytest.raises(ValueError, match="namespace"):
        ClusterRef(namespace=" ")


def test_chart_input_rejects_empty_chart() -> None:
    with pytest.raises(ValueError, match="chart"):
        ChartInput(chart=" ")


def test_plan_request_rejects_overlapping_filters() -> None:
    with pytest.raises(ValueError, match="included and excluded"):
        PlanRequest(
            source=ChartInput(chart="source"),
            destination=ChartInput(chart="dest"),
            source_cluster=ClusterRef(namespace="src"),
            destination_cluster=ClusterRef(namespace="dst"),
            include_workloads=("app",),
            exclude_workloads=("app",),
        )


def test_empty_plan_is_not_executable() -> None:
    plan = MigrationPlan(
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        workload_plans=(),
    )
    assert plan.executable is False
