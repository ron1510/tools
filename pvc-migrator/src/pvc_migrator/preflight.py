from __future__ import annotations

import shutil
import subprocess

from pvc_migrator.models import ClusterRef, PreflightCheck


def run_preflight(
    *,
    source_cluster: ClusterRef,
    destination_cluster: ClusterRef,
    required_binaries: tuple[str, ...],
) -> tuple[PreflightCheck, ...]:
    checks: list[PreflightCheck] = []
    for binary in required_binaries:
        checks.append(_check_binary(binary))
    checks.extend(_check_cluster_access(source_cluster, role="source"))
    checks.extend(_check_cluster_access(destination_cluster, role="destination"))
    return tuple(checks)


def summarize_blockers(checks: tuple[PreflightCheck, ...]) -> tuple[str, ...]:
    return tuple(check.detail for check in checks if check.status == "blocked")


def summarize_warnings(checks: tuple[PreflightCheck, ...]) -> tuple[str, ...]:
    return tuple(check.detail for check in checks if check.status == "warning")


def _check_binary(binary: str) -> PreflightCheck:
    if shutil.which(binary) is None:
        return PreflightCheck(
            name=f"binary:{binary}",
            status="blocked",
            detail=f"required binary not found on PATH: {binary}",
        )
    return PreflightCheck(
        name=f"binary:{binary}",
        status="ok",
        detail=f"found required binary: {binary}",
    )


def _check_cluster_access(cluster: ClusterRef, *, role: str) -> tuple[PreflightCheck, ...]:
    base = ["kubectl"]
    if cluster.context:
        base.extend(["--context", cluster.context])
    checks: list[PreflightCheck] = []
    checks.append(
        _run_can_i(
            base + ["auth", "can-i", "get", "pvc", "-n", cluster.namespace],
            name=f"{role}:can-get-pvc",
            success_detail=f"{role} cluster can get PVCs in namespace {cluster.namespace}",
            failure_detail=f"{role} cluster cannot get PVCs in namespace {cluster.namespace}",
        )
    )
    checks.append(
        _run_can_i(
            base + ["auth", "can-i", "get", "statefulset", "-n", cluster.namespace],
            name=f"{role}:can-get-statefulset",
            success_detail=f"{role} cluster can get StatefulSets in namespace {cluster.namespace}",
            failure_detail=f"{role} cluster cannot get StatefulSets in namespace {cluster.namespace}",
        )
    )
    checks.append(
        _run_can_i(
            base + ["auth", "can-i", "create", "pod", "-n", cluster.namespace],
            name=f"{role}:can-create-pod",
            success_detail=f"{role} cluster can create Pods in namespace {cluster.namespace}",
            failure_detail=f"{role} cluster may be unable to create helper Pods in namespace {cluster.namespace}",
            warning_on_failure=True,
        )
    )
    return tuple(checks)


def _run_can_i(
    command: list[str],
    *,
    name: str,
    success_detail: str,
    failure_detail: str,
    warning_on_failure: bool = False,
) -> PreflightCheck:
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        return PreflightCheck(
            name=name,
            status="warning" if warning_on_failure else "blocked",
            detail=f"{failure_detail}; verification failed: {exc}",
        )
    allowed = completed.stdout.strip().lower() == "yes"
    if allowed:
        return PreflightCheck(name=name, status="ok", detail=success_detail)
    return PreflightCheck(
        name=name,
        status="warning" if warning_on_failure else "blocked",
        detail=failure_detail,
    )
