from __future__ import annotations

from pvc_migrator.models import (
    ClusterRef,
    EngineName,
    MigrationCommand,
    PlanRequest,
    PvcPair,
    WorkloadCategory,
    WorkloadInfo,
    WorkloadPlan,
    as_engine_name,
)


def build_workload_plan(
    request: PlanRequest,
    source_cluster: ClusterRef,
    destination_cluster: ClusterRef,
    source_workload: WorkloadInfo,
    destination_workload: WorkloadInfo,
    pvc_pairs: tuple[PvcPair, ...],
) -> WorkloadPlan:
    category = source_workload.category
    engine: EngineName = _choose_engine(category)
    warnings: list[str] = list(source_workload.notes)
    blockers: list[str] = []

    if request.engine_override and request.engine_override != "auto":
        if category == "victoriametrics-vmstorage" and request.engine_override == "pv-migrate":
            blockers.append("refusing to force pv-migrate for VictoriaMetrics vmstorage")
        else:
            engine = as_engine_name(request.engine_override)

    commands: tuple[MigrationCommand, ...]
    if engine == "pv-migrate":
        commands = _build_pv_migrate_commands(source_cluster, destination_cluster, pvc_pairs)
        if source_workload.category == "generic":
            warnings.append("Generic PVC migration may require workload quiescing for consistency.")
    elif engine == "victoriametrics-vmstorage":
        commands = _build_vmstorage_commands(source_workload, destination_workload)
    elif engine == "arangodb-native":
        commands = _build_arangodb_commands(
            source_cluster,
            destination_cluster,
            source_workload,
            destination_workload,
        )
    elif engine == "grafana-plugins":
        commands = _build_grafana_commands(source_workload, pvc_pairs)
    else:
        commands = ()

    if engine == "victoriametrics-aux-skip":
        warnings.append("vmagent/vmalert are usually better re-rendered and redeployed than PVC-migrated.")
        if request.allow_aux_pvc_copy and pvc_pairs:
            commands = _build_pv_migrate_commands(source_cluster, destination_cluster, pvc_pairs)
            engine = "pv-migrate"
            warnings.append("Auxiliary VictoriaMetrics PVC copy was explicitly enabled.")
        else:
            commands = ()

    if engine == "grafana-plugins" and source_workload.plugin_declarations:
        warnings.append("Grafana plugins are declared in values; prefer destination redeploy over file copy.")

    return WorkloadPlan(
        workload_name=source_workload.name,
        destination_workload_name=destination_workload.name,
        category=category,
        engine=engine,
        pvc_pairs=pvc_pairs,
        commands=commands,
        warnings=tuple(warnings),
        blockers=tuple(blockers),
    )


def _choose_engine(category: WorkloadCategory) -> EngineName:
    if category == "victoriametrics-vmstorage":
        return "victoriametrics-vmstorage"
    if category == "victoriametrics-aux":
        return "victoriametrics-aux-skip"
    if category == "arangodb-single":
        return "arangodb-native"
    if category == "grafana":
        return "grafana-plugins"
    return "pv-migrate"


def _build_pv_migrate_commands(
    source_cluster: ClusterRef,
    destination_cluster: ClusterRef,
    pvc_pairs: tuple[PvcPair, ...],
) -> tuple[MigrationCommand, ...]:
    commands: list[MigrationCommand] = []
    for pair in pvc_pairs:
        command = (
            "pv-migrate migrate "
            f"--source-context {source_cluster.context or '<current>'} "
            f"--source-namespace {pair.source_namespace} "
            f"--source {pair.source_name} "
            f"--dest-context {destination_cluster.context or '<current>'} "
            f"--dest-namespace {pair.destination_namespace} "
            f"--dest {pair.destination_name}"
        )
        commands.append(
            MigrationCommand(
                description=f"Copy PVC {pair.source_name} to {pair.destination_name}",
                command=command,
            )
        )
    return tuple(commands)


def _build_vmstorage_commands(
    source_workload: WorkloadInfo,
    destination_workload: WorkloadInfo,
) -> tuple[MigrationCommand, ...]:
    return (
        MigrationCommand(
            description=f"Create vmbackup snapshot inside {source_workload.name}",
            command=(
                f"kubectl exec statefulset/{source_workload.name} -c vmbackup -- "
                "sh -lc \"rm -rf /vmbackup-data/latest /tmp/vmbackup-latest.tar "
                "&& rm -f /vmbackup-data/vmbackup-latest.tar "
                "&& /vmbackup-prod -storageDataPath=/vmstorage-data "
                "-snapshot.createURL=http://127.0.0.1:8482/snapshot/create "
                "-dst=fs:///vmbackup-data/latest "
                "&& tar -C /vmbackup-data -cf /vmbackup-data/vmbackup-latest.tar latest\""
            ),
        ),
        MigrationCommand(
            description=f"Copy vmbackup artifact from {source_workload.name} to local run artifacts",
            command=f"kubectl cp <source-vmbackup-pod>:/vmbackup-data/vmbackup-latest.tar .pvc-migrator-runs/{source_workload.name}-vmbackup-latest.tar",
        ),
        MigrationCommand(
            description=f"Scale down destination StatefulSet {destination_workload.name}",
            command=f"kubectl scale statefulset/{destination_workload.name} --replicas=0",
        ),
        MigrationCommand(
            description=f"Restore backup into destination PVCs for {destination_workload.name}",
            command=(
                f"create helper pod with victoriametrics/vmrestore, mount destination PVC, "
                f"copy .pvc-migrator-runs/{source_workload.name}-vmbackup-latest.tar, "
                "extract it, and run "
                "/vmrestore-prod -src=fs:///tmp/vmbackup/latest -storageDataPath=/vmstorage-data"
            ),
        ),
        MigrationCommand(
            description=f"Scale destination StatefulSet {destination_workload.name} back to 1",
            command=f"kubectl scale statefulset/{destination_workload.name} --replicas=1",
        ),
    )


def _build_arangodb_commands(
    source_cluster: ClusterRef,
    destination_cluster: ClusterRef,
    source_workload: WorkloadInfo,
    destination_workload: WorkloadInfo,
) -> tuple[MigrationCommand, ...]:
    source_context = (
        f"--context {source_cluster.context} " if source_cluster.context else ""
    )
    destination_context = (
        f"--context {destination_cluster.context} " if destination_cluster.context else ""
    )
    source_ref = _kubectl_workload_ref(source_workload)
    destination_ref = _kubectl_workload_ref(destination_workload)
    artifact_path = f".pvc-migrator-runs/arangodb-{source_workload.name}.tar"
    return (
        MigrationCommand(
            description=f"Create ArangoDB dump inside {source_workload.name}",
            command=(
                f"kubectl {source_context}-n {source_cluster.namespace} exec {source_ref} -- "
                "sh -lc \"rm -rf /tmp/pvc-migrator-dump "
                "&& arangodump --server.endpoint tcp://127.0.0.1:8529 --server.authentication false --all-databases true "
                "--output-directory /tmp/pvc-migrator-dump "
                "&& tar -C /tmp -cf /tmp/pvc-migrator-dump.tar pvc-migrator-dump\""
            ),
        ),
        MigrationCommand(
            description=f"Copy ArangoDB dump from {source_workload.name} to local artifact",
            command=(
                f"kubectl {source_context}-n {source_cluster.namespace} cp "
                f"{source_workload.name}-$(kubectl {source_context}-n {source_cluster.namespace} get pods "
                f"-l app.kubernetes.io/name={source_workload.name} -o jsonpath='{{.items[0].metadata.name}}'):/tmp/pvc-migrator-dump.tar "
                f"{artifact_path}"
            ),
        ),
        MigrationCommand(
            description=f"Copy local ArangoDB dump artifact into {destination_workload.name}",
            command=(
                f"kubectl {destination_context}-n {destination_cluster.namespace} cp "
                f"{artifact_path} "
                f"{destination_workload.name}-$(kubectl {destination_context}-n {destination_cluster.namespace} get pods "
                f"-l app.kubernetes.io/name={destination_workload.name} -o jsonpath='{{.items[0].metadata.name}}'):/tmp/pvc-migrator-dump.tar"
            ),
        ),
        MigrationCommand(
            description=f"Restore ArangoDB dump into {destination_workload.name}",
            command=(
                f"kubectl {destination_context}-n {destination_cluster.namespace} exec {destination_ref} -- "
                "sh -lc \"rm -rf /tmp/pvc-migrator-dump "
                "&& mkdir -p /tmp "
                "&& tar -C /tmp -xf /tmp/pvc-migrator-dump.tar "
                "&& arangorestore --server.endpoint tcp://127.0.0.1:8529 --server.authentication false --all-databases true "
                "--input-directory /tmp/pvc-migrator-dump --create-database true --overwrite true\""
            ),
        ),
    )


def _build_grafana_commands(
    workload: WorkloadInfo,
    pvc_pairs: tuple[PvcPair, ...],
) -> tuple[MigrationCommand, ...]:
    if workload.plugin_declarations:
        return (
            MigrationCommand(
                description="Redeploy Grafana with declared plugins from values",
                command="helm upgrade <release> <chart> -f <values-with-plugins>",
            ),
        )
    return tuple(
        MigrationCommand(
            description=f"Copy Grafana plugin PVC {pair.source_name} to {pair.destination_name}",
            command=(
                "pv-migrate migrate "
                f"--source {pair.source_name} --dest {pair.destination_name}"
            ),
        )
        for pair in pvc_pairs
    )


def _kubectl_workload_ref(workload: WorkloadInfo) -> str:
    if workload.kind == "StatefulSet":
        return f"statefulset/{workload.name}"
    return f"deployment/{workload.name}"
