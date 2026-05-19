from __future__ import annotations

from typing import Any

import pytest

from pvc_migrator.errors import ExecutionBlockedError
from pvc_migrator.models import (
    ClusterRef,
    CommandExecutionRecord,
    MigrationCommand,
    MigrationPlan,
    PreflightCheck,
    WorkloadPlan,
)
from pvc_migrator.runlog import RunLogStore
from pvc_migrator.service import MigrationPlannerService


class RunnerSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, command: str) -> None:
        self.calls.append(command)


def no_preflight(**kwargs: Any) -> tuple[PreflightCheck, ...]:
    del kwargs
    return ()


def test_execute_plan_blocks_non_executable_plan() -> None:
    plan = MigrationPlan(
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        workload_plans=(WorkloadPlan(workload_name="db", category="generic", engine="pv-migrate"),),
        blockers=("blocked",),
    )
    with pytest.raises(ExecutionBlockedError, match="refusing to execute"):
        MigrationPlannerService().execute_plan(plan)


def test_execute_plan_requires_approval() -> None:
    plan = MigrationPlan(
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        workload_plans=(
            WorkloadPlan(
                workload_name="db",
                category="generic",
                engine="pv-migrate",
                commands=(MigrationCommand(description="copy", command="pv-migrate migrate"),),
            ),
        ),
    )
    with pytest.raises(ExecutionBlockedError, match="explicit approval"):
        MigrationPlannerService().execute_plan(plan, approved=False)


def test_execute_plan_runs_commands() -> None:
    runner = RunnerSpy()
    plan = MigrationPlan(
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        workload_plans=(
            WorkloadPlan(
                workload_name="db",
                category="generic",
                engine="pv-migrate",
                commands=(MigrationCommand(description="copy", command="pv-migrate migrate"),),
            ),
        ),
    )
    result = MigrationPlannerService(runner=runner, preflight_runner=no_preflight).execute_plan(
        plan,
        approved=True,
    )
    assert runner.calls == ["pv-migrate migrate"]
    assert result.commands_run == ("pv-migrate migrate",)


def test_execute_plan_resumes_completed_commands(tmp_path: str) -> None:
    runner = RunnerSpy()
    store = RunLogStore(root=tmp_path)
    service = MigrationPlannerService(runner=runner, runlog_store=store, preflight_runner=no_preflight)
    plan = MigrationPlan(
        run_id="run123",
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        workload_plans=(
            WorkloadPlan(
                workload_name="db",
                category="generic",
                engine="pv-migrate",
                commands=(
                    MigrationCommand(description="one", command="cmd-one"),
                    MigrationCommand(description="two", command="cmd-two"),
                ),
            ),
        ),
    )
    store.append_record(
        "run123",
        "src->dst",
        record=CommandExecutionRecord(
            workload_name="db",
            command="cmd-one",
            description="one",
            status="completed",
        ),
    )
    result = service.execute_plan(plan, approved=True, resume_run_id="run123")
    assert runner.calls == ["cmd-two"]
    assert result.commands_run == ("cmd-two",)


def test_execute_plan_can_filter_workloads(tmp_path: str) -> None:
    runner = RunnerSpy()
    store = RunLogStore(root=tmp_path)
    service = MigrationPlannerService(runner=runner, runlog_store=store, preflight_runner=no_preflight)
    plan = MigrationPlan(
        run_id="run123",
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        workload_plans=(
            WorkloadPlan(
                workload_name="db",
                category="generic",
                engine="pv-migrate",
                commands=(MigrationCommand(description="one", command="cmd-one"),),
            ),
            WorkloadPlan(
                workload_name="cache",
                category="generic",
                engine="pv-migrate",
                commands=(MigrationCommand(description="two", command="cmd-two"),),
            ),
        ),
    )
    result = service.execute_plan(plan, approved=True, selected_workloads=("cache",))
    assert runner.calls == ["cmd-two"]
    assert "db" in result.skipped_workloads
