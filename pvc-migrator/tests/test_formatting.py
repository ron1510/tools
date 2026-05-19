from __future__ import annotations

import json

import yaml

from pvc_migrator.formatting import render_plan
from pvc_migrator.models import ClusterRef, MigrationCommand, MigrationPlan, WorkloadPlan


def make_plan() -> MigrationPlan:
    return MigrationPlan(
        source_cluster=ClusterRef(namespace="src", context="c1"),
        destination_cluster=ClusterRef(namespace="dst", context="c2"),
        workload_plans=(
            WorkloadPlan(
                workload_name="db",
                category="generic",
                engine="pv-migrate",
                commands=(MigrationCommand(description="x", command="pv-migrate migrate"),),
            ),
        ),
    )


def test_render_plan_json() -> None:
    payload = json.loads(render_plan(make_plan(), "json"))
    assert payload["source_cluster"]["namespace"] == "src"


def test_render_plan_yaml() -> None:
    payload = yaml.safe_load(render_plan(make_plan(), "yaml"))
    assert payload["destination_cluster"]["namespace"] == "dst"


def test_render_plan_table_includes_executable() -> None:
    output = render_plan(make_plan(), "table")
    assert "Executable: yes" in output
    assert "[db] pv-migrate" in output
