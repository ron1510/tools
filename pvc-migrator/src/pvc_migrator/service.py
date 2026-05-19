from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import subprocess
import uuid
from typing import Protocol

from pvc_migrator.discovery import ClusterInspector, discover_workloads
from pvc_migrator.engines import build_workload_plan
from pvc_migrator.errors import ExecutionBlockedError, PlanValidationError
from pvc_migrator.mapping import build_pvc_pairs, pair_workloads
from pvc_migrator.mapping_overrides import load_mapping_overrides
from pvc_migrator.models import (
    CommandExecutionRecord,
    ExecuteResult,
    MigrationPlan,
    PlanRequest,
    PreflightCheck,
    WorkloadInfo,
    WorkloadPlan,
    parse_rendered_resources,
)
from pvc_migrator.preflight import run_preflight, summarize_blockers, summarize_warnings
from pvc_migrator.rendering import HelmRenderer, load_values_summary
from pvc_migrator.runlog import RunLogStore
from pvc_migrator.runner import CommandRunner


class MigrationPlannerService:
    def __init__(
        self,
        renderer: HelmRenderer | None = None,
        inspector: ClusterInspector | None = None,
        runner: CommandRunner | None = None,
        runlog_store: RunLogStore | None = None,
        preflight_runner: Callable[..., tuple[PreflightCheck, ...]] | None = None,
    ) -> None:
        self._renderer = renderer or HelmRenderer()
        self._inspector = inspector or ClusterInspector()
        self._runner = runner or CommandRunner()
        self._runlog_store = runlog_store or RunLogStore()
        self._preflight_runner = preflight_runner or run_preflight

    def build_plan(self, request: PlanRequest) -> MigrationPlan:
        run_id = uuid.uuid4().hex[:12]
        source_resources = parse_rendered_resources(list(self._renderer.render(request.source)))
        destination_resources = parse_rendered_resources(list(self._renderer.render(request.destination)))
        source_values = load_values_summary(request.source.values_file)
        destination_values = load_values_summary(request.destination.values_file)
        overrides = load_mapping_overrides(request.mapping_file)
        source_workloads = discover_workloads(source_resources, source_values, request.source)
        destination_workloads = discover_workloads(destination_resources, destination_values, request.destination)

        filtered_source = _filter_workloads(source_workloads, request)
        filtered_destination = _filter_workloads(destination_workloads, request)

        preflight_checks = self._preflight_runner(
            source_cluster=request.source_cluster,
            destination_cluster=request.destination_cluster,
            required_binaries=_required_binaries(request, filtered_source),
        )
        source_live = self._inspector.list_pvcs(request.source_cluster, request.extra_pvc_selector)
        destination_live = self._inspector.list_pvcs(request.destination_cluster, request.extra_pvc_selector)

        pairs = pair_workloads(filtered_source, filtered_destination, overrides=overrides)
        workload_plans: list[WorkloadPlan] = []
        blockers: list[str] = list(summarize_blockers(preflight_checks))
        warnings: list[str] = list(summarize_warnings(preflight_checks))
        for pair in pairs:
            try:
                pvc_pairs = build_pvc_pairs(pair, source_live, destination_live, overrides=overrides)
            except PlanValidationError as exc:
                workload_plans.append(
                    build_workload_plan(
                        request,
                        request.source_cluster,
                        request.destination_cluster,
                        pair.source,
                        pair.destination,
                        (),
                    ).model_copy(update={"blockers": (str(exc),)})
                )
                blockers.append(str(exc))
                continue
            workload_plan = build_workload_plan(
                request,
                request.source_cluster,
                request.destination_cluster,
                pair.source,
                pair.destination,
                pvc_pairs,
            )
            workload_plans.append(workload_plan)
            warnings.extend(workload_plan.warnings)
            blockers.extend(workload_plan.blockers)

        if not workload_plans:
            blockers.append("no workloads matched the requested selection")

        return MigrationPlan(
            run_id=run_id,
            source_cluster=request.source_cluster,
            destination_cluster=request.destination_cluster,
            workload_plans=tuple(workload_plans),
            preflight_checks=preflight_checks,
            warnings=tuple(dict.fromkeys(warnings)),
            blockers=tuple(dict.fromkeys(blockers)),
        )

    def execute_plan(
        self,
        plan: MigrationPlan,
        *,
        approved: bool = False,
        selected_workloads: tuple[str, ...] = (),
        resume_run_id: str | None = None,
    ) -> ExecuteResult:
        if not plan.executable:
            raise ExecutionBlockedError("plan has blockers; refusing to execute")
        if not approved:
            raise ExecutionBlockedError("execute requires explicit approval via --approve")

        run_id = resume_run_id or plan.run_id
        completed_commands = self._runlog_store.completed_commands(run_id)
        commands_run: list[str] = []
        skipped: list[str] = []
        plan_summary = f"{plan.source_cluster.namespace}->{plan.destination_cluster.namespace}"

        for workload_plan in plan.workload_plans:
            if selected_workloads and workload_plan.workload_name not in selected_workloads:
                skipped.append(workload_plan.workload_name)
                continue
            if not workload_plan.commands:
                skipped.append(workload_plan.workload_name)
                continue
            if workload_plan.engine == "victoriametrics-vmstorage":
                self._execute_vmstorage_native(
                    plan,
                    workload_plan,
                    run_id=run_id,
                    plan_summary=plan_summary,
                    completed_commands=completed_commands,
                    commands_run=commands_run,
                )
                continue
            if workload_plan.engine == "arangodb-native":
                self._execute_arangodb_native(
                    plan,
                    workload_plan,
                    run_id=run_id,
                    plan_summary=plan_summary,
                    completed_commands=completed_commands,
                    commands_run=commands_run,
                )
                continue
            for command in workload_plan.commands:
                if command.command in completed_commands:
                    self._runlog_store.append_record(
                        run_id,
                        plan_summary,
                        CommandExecutionRecord(
                            workload_name=workload_plan.workload_name,
                            command=command.command,
                            description=command.description,
                            status="skipped",
                            error="already completed in prior run",
                        ),
                    )
                    continue
                try:
                    self._runner.run(command.command)
                except Exception as exc:
                    self._runlog_store.append_record(
                        run_id,
                        plan_summary,
                        CommandExecutionRecord(
                            workload_name=workload_plan.workload_name,
                            command=command.command,
                            description=command.description,
                            status="failed",
                            error=str(exc),
                        ),
                    )
                    raise
                self._runlog_store.append_record(
                    run_id,
                    plan_summary,
                    CommandExecutionRecord(
                        workload_name=workload_plan.workload_name,
                        command=command.command,
                        description=command.description,
                        status="completed",
                    ),
                )
                commands_run.append(command.command)
        return ExecuteResult(commands_run=tuple(commands_run), skipped_workloads=tuple(skipped))

    def _execute_vmstorage_native(
        self,
        plan: MigrationPlan,
        workload_plan: WorkloadPlan,
        *,
        run_id: str,
        plan_summary: str,
        completed_commands: set[str],
        commands_run: list[str],
    ) -> None:
        destination_name = workload_plan.destination_workload_name
        if destination_name is None:
            raise ExecutionBlockedError("victoriametrics-vmstorage workload is missing destination workload name")
        if not workload_plan.pvc_pairs:
            raise ExecutionBlockedError("victoriametrics-vmstorage workload is missing destination PVC mapping")

        artifact_dir = Path(".pvc-migrator-runs")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{workload_plan.workload_name}-vmbackup-latest.tar"
        source_context = plan.source_cluster.context
        destination_context = plan.destination_cluster.context
        source_pod = self._get_pod_name(plan.source_cluster.namespace, workload_plan.workload_name, source_context)
        destination_pvc = workload_plan.pvc_pairs[0].destination_name
        helper_pod = f"vmrestore-{run_id}-{workload_plan.workload_name}"[:63]
        helper_manifest = self._build_vmrestore_helper_manifest(
            helper_pod,
            destination_pvc,
            plan.destination_cluster.namespace,
        )
        steps = (
            (
                workload_plan.commands[0],
                [
                    "kubectl",
                    *([] if source_context is None else ["--context", source_context]),
                    "-n",
                    plan.source_cluster.namespace,
                    "exec",
                    f"pod/{source_pod}",
                    "-c",
                    "vmbackup",
                    "--",
                    "sh",
                    "-lc",
                    (
                        "rm -rf /vmbackup-data/latest /tmp/vmbackup-latest.tar "
                        "&& rm -f /vmbackup-data/vmbackup-latest.tar "
                        "&& /vmbackup-prod -storageDataPath=/vmstorage-data "
                        "-snapshot.createURL=http://127.0.0.1:8482/snapshot/create "
                        "-dst=fs:///vmbackup-data/latest "
                        "&& tar -C /vmbackup-data -cf /vmbackup-data/vmbackup-latest.tar latest"
                    ),
                ],
            ),
            (
                workload_plan.commands[1],
                [
                    "kubectl",
                    *([] if source_context is None else ["--context", source_context]),
                    "-n",
                    plan.source_cluster.namespace,
                    "cp",
                    f"{source_pod}:/vmbackup-data/vmbackup-latest.tar",
                    str(artifact_path),
                ],
            ),
            (
                workload_plan.commands[2],
                [
                    "kubectl",
                    *([] if destination_context is None else ["--context", destination_context]),
                    "-n",
                    plan.destination_cluster.namespace,
                    "scale",
                    f"statefulset/{destination_name}",
                    "--replicas=0",
                ],
            ),
        )
        self._run_native_steps(run_id, plan_summary, workload_plan.workload_name, steps, completed_commands, commands_run)

        create_helper_command = workload_plan.commands[3].command
        if create_helper_command not in completed_commands:
            self._apply_manifest(helper_manifest, destination_context)
            self._wait_for_pod_ready(plan.destination_cluster.namespace, helper_pod, destination_context)
            self._runlog_store.append_record(
                run_id,
                plan_summary,
                CommandExecutionRecord(
                    workload_name=workload_plan.workload_name,
                    command=create_helper_command,
                    description=workload_plan.commands[3].description,
                    status="completed",
                ),
            )
            commands_run.append(create_helper_command)
        else:
            self._runlog_store.append_record(
                run_id,
                plan_summary,
                CommandExecutionRecord(
                    workload_name=workload_plan.workload_name,
                    command=create_helper_command,
                    description=workload_plan.commands[3].description,
                    status="skipped",
                    error="already completed in prior run",
                ),
            )

        restore_steps = (
            (
                MigrationCommandPlaceholder(workload_plan.commands[3].command + "#copy"),
                [
                    "kubectl",
                    *([] if destination_context is None else ["--context", destination_context]),
                    "-n",
                    plan.destination_cluster.namespace,
                    "cp",
                    str(artifact_path),
                    f"{helper_pod}:/tmp/vmbackup-latest.tar",
                ],
            ),
            (
                MigrationCommandPlaceholder(workload_plan.commands[3].command + "#restore"),
                [
                    "kubectl",
                    *([] if destination_context is None else ["--context", destination_context]),
                    "-n",
                    plan.destination_cluster.namespace,
                    "exec",
                    f"pod/{helper_pod}",
                    "--",
                    "sh",
                    "-lc",
                    (
                        "rm -rf /tmp/vmbackup "
                        "&& mkdir -p /tmp/vmbackup "
                        "&& tar -C /tmp/vmbackup -xf /tmp/vmbackup-latest.tar "
                        "&& /vmrestore-prod -src=fs:///tmp/vmbackup/latest -storageDataPath=/vmstorage-data"
                    ),
                ],
            ),
        )
        self._run_native_steps(run_id, plan_summary, workload_plan.workload_name, restore_steps, completed_commands, commands_run)

        delete_helper_command = workload_plan.commands[3].command + "#cleanup"
        if delete_helper_command not in completed_commands:
            subprocess.run(
                [
                    "kubectl",
                    *([] if destination_context is None else ["--context", destination_context]),
                    "-n",
                    plan.destination_cluster.namespace,
                    "delete",
                    "pod",
                    helper_pod,
                    "--ignore-not-found=true",
                ],
                check=True,
            )
            self._runlog_store.append_record(
                run_id,
                plan_summary,
                CommandExecutionRecord(
                    workload_name=workload_plan.workload_name,
                    command=delete_helper_command,
                    description="Delete vmrestore helper pod",
                    status="completed",
                ),
            )
            commands_run.append(delete_helper_command)

        scale_up = (
            (
                workload_plan.commands[4],
                [
                    "kubectl",
                    *([] if destination_context is None else ["--context", destination_context]),
                    "-n",
                    plan.destination_cluster.namespace,
                    "scale",
                    f"statefulset/{destination_name}",
                    "--replicas=1",
                ],
            ),
        )
        self._run_native_steps(run_id, plan_summary, workload_plan.workload_name, scale_up, completed_commands, commands_run)
        self._wait_for_rollout(plan.destination_cluster.namespace, f"statefulset/{destination_name}", destination_context)

    def _execute_arangodb_native(
        self,
        plan: MigrationPlan,
        workload_plan: WorkloadPlan,
        *,
        run_id: str,
        plan_summary: str,
        completed_commands: set[str],
        commands_run: list[str],
    ) -> None:
        destination_name = workload_plan.destination_workload_name
        if destination_name is None:
            raise ExecutionBlockedError("arangodb-native workload is missing destination workload name")

        artifact_dir = Path(".pvc-migrator-runs")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"arangodb-{workload_plan.workload_name}.tar"
        source_context = plan.source_cluster.context
        destination_context = plan.destination_cluster.context
        source_pod = self._get_pod_name(plan.source_cluster.namespace, workload_plan.workload_name, source_context)
        destination_pod = self._get_pod_name(plan.destination_cluster.namespace, destination_name, destination_context)
        steps = (
            (
                workload_plan.commands[0],
                [
                    "kubectl",
                    *([] if source_context is None else ["--context", source_context]),
                    "-n",
                    plan.source_cluster.namespace,
                    "exec",
                    f"pod/{source_pod}",
                    "--",
                    "sh",
                    "-lc",
                    (
                        "rm -rf /tmp/pvc-migrator-dump "
                        "&& arangodump --server.endpoint tcp://127.0.0.1:8529 --server.authentication false --all-databases true "
                        "--output-directory /tmp/pvc-migrator-dump "
                        "&& tar -C /tmp -cf /tmp/pvc-migrator-dump.tar pvc-migrator-dump"
                    ),
                ],
            ),
            (
                workload_plan.commands[1],
                [
                    "kubectl",
                    *([] if source_context is None else ["--context", source_context]),
                    "-n",
                    plan.source_cluster.namespace,
                    "cp",
                    f"{source_pod}:/tmp/pvc-migrator-dump.tar",
                    str(artifact_path),
                ],
            ),
            (
                workload_plan.commands[2],
                [
                    "kubectl",
                    *([] if destination_context is None else ["--context", destination_context]),
                    "-n",
                    plan.destination_cluster.namespace,
                    "cp",
                    str(artifact_path),
                    f"{destination_pod}:/tmp/pvc-migrator-dump.tar",
                ],
            ),
            (
                workload_plan.commands[3],
                [
                    "kubectl",
                    *([] if destination_context is None else ["--context", destination_context]),
                    "-n",
                    plan.destination_cluster.namespace,
                    "exec",
                    f"pod/{destination_pod}",
                    "--",
                    "sh",
                    "-lc",
                    (
                        "rm -rf /tmp/pvc-migrator-dump "
                        "&& mkdir -p /tmp "
                        "&& tar -C /tmp -xf /tmp/pvc-migrator-dump.tar "
                        "&& arangorestore --server.endpoint tcp://127.0.0.1:8529 --server.authentication false --all-databases true "
                        "--input-directory /tmp/pvc-migrator-dump --create-database true --overwrite true"
                    ),
                ],
            ),
        )
        for command, argv in steps:
            if command.command in completed_commands:
                self._runlog_store.append_record(
                    run_id,
                    plan_summary,
                    CommandExecutionRecord(
                        workload_name=workload_plan.workload_name,
                        command=command.command,
                        description=command.description,
                        status="skipped",
                        error="already completed in prior run",
                    ),
                )
                continue
            try:
                subprocess.run(argv, check=True)
            except Exception as exc:
                self._runlog_store.append_record(
                    run_id,
                    plan_summary,
                    CommandExecutionRecord(
                        workload_name=workload_plan.workload_name,
                        command=command.command,
                        description=command.description,
                        status="failed",
                        error=str(exc),
                    ),
                )
                raise
            self._runlog_store.append_record(
                run_id,
                plan_summary,
                CommandExecutionRecord(
                    workload_name=workload_plan.workload_name,
                    command=command.command,
                    description=command.description,
                    status="completed",
                ),
            )
            commands_run.append(command.command)

    def _run_native_steps(
        self,
        run_id: str,
        plan_summary: str,
        workload_name: str,
        steps: tuple[tuple["CommandLike", list[str]], ...],
        completed_commands: set[str],
        commands_run: list[str],
    ) -> None:
        for command_obj, argv in steps:
            command_text = command_obj.command
            description = command_obj.description
            if command_text in completed_commands:
                self._runlog_store.append_record(
                    run_id,
                    plan_summary,
                    CommandExecutionRecord(
                        workload_name=workload_name,
                        command=command_text,
                        description=description,
                        status="skipped",
                        error="already completed in prior run",
                    ),
                )
                continue
            try:
                subprocess.run(argv, check=True)
            except Exception as exc:
                self._runlog_store.append_record(
                    run_id,
                    plan_summary,
                    CommandExecutionRecord(
                        workload_name=workload_name,
                        command=command_text,
                        description=description,
                        status="failed",
                        error=str(exc),
                    ),
                )
                raise
            self._runlog_store.append_record(
                run_id,
                plan_summary,
                CommandExecutionRecord(
                    workload_name=workload_name,
                    command=command_text,
                    description=description,
                    status="completed",
                ),
            )
            commands_run.append(command_text)

    def _get_pod_name(self, namespace: str, workload_name: str, context: str | None) -> str:
        command = [
            "kubectl",
            *([] if context is None else ["--context", context]),
            "-n",
            namespace,
            "get",
            "pods",
            "-l",
            f"app.kubernetes.io/name={workload_name}",
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        pod_name = completed.stdout.strip()
        if not pod_name:
            raise ExecutionBlockedError(f"no pod found for workload {workload_name} in namespace {namespace}")
        return pod_name

    def _apply_manifest(self, manifest: str, context: str | None) -> None:
        subprocess.run(
            ["kubectl", *([] if context is None else ["--context", context]), "apply", "-f", "-"],
            input=manifest,
            text=True,
            check=True,
        )

    def _wait_for_pod_ready(self, namespace: str, pod_name: str, context: str | None) -> None:
        subprocess.run(
            [
                "kubectl",
                *([] if context is None else ["--context", context]),
                "-n",
                namespace,
                "wait",
                "--for=condition=Ready",
                f"pod/{pod_name}",
                "--timeout=240s",
            ],
            check=True,
        )

    def _wait_for_rollout(self, namespace: str, ref: str, context: str | None) -> None:
        subprocess.run(
            [
                "kubectl",
                *([] if context is None else ["--context", context]),
                "-n",
                namespace,
                "rollout",
                "status",
                ref,
                "--timeout=240s",
            ],
            check=True,
        )

    def _build_vmrestore_helper_manifest(self, pod_name: str, pvc_name: str, namespace: str) -> str:
        return f"""apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {namespace}
spec:
  restartPolicy: Never
  containers:
    - name: vmrestore
      image: victoriametrics/vmrestore:latest
      command: ["/bin/sh", "-c", "sleep infinity"]
      volumeMounts:
        - name: restore-target
          mountPath: /vmstorage-data
  volumes:
    - name: restore-target
      persistentVolumeClaim:
        claimName: {pvc_name}
"""


class MigrationCommandPlaceholder:
    def __init__(self, command: str, description: str = "Internal native step") -> None:
        self.command = command
        self.description = description


class CommandLike(Protocol):
    command: str
    description: str


def _filter_workloads(
    workloads: tuple[WorkloadInfo, ...],
    request: PlanRequest,
) -> tuple[WorkloadInfo, ...]:
    included = list(workloads)
    if request.include_workloads:
        included = [
            workload
            for workload in included
            if workload.name in request.include_workloads
            or workload.category in request.include_workloads
        ]
    if request.exclude_workloads:
        included = [
            workload
            for workload in included
            if workload.name not in request.exclude_workloads
            and workload.category not in request.exclude_workloads
        ]
    return tuple(included)


def _required_binaries(
    request: PlanRequest,
    workloads: tuple[WorkloadInfo, ...],
) -> tuple[str, ...]:
    binaries = {"helm", "kubectl"}
    if request.engine_override == "pv-migrate":
        binaries.add("pv-migrate")
    elif request.engine_override in (None, "auto"):
        for workload in workloads:
            if workload.category == "generic":
                binaries.add("pv-migrate")
            if workload.category == "victoriametrics-aux" and request.allow_aux_pvc_copy:
                binaries.add("pv-migrate")
            if workload.category == "grafana" and not workload.plugin_declarations:
                binaries.add("pv-migrate")
    return tuple(sorted(binaries))
