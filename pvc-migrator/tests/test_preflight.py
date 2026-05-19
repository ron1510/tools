from __future__ import annotations

import subprocess
from typing import Any

import pytest

from pvc_migrator.models import ClusterRef
from pvc_migrator.preflight import run_preflight


def test_preflight_blocks_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pvc_migrator.preflight.shutil.which", lambda name: None if name == "pv-migrate" else "x")
    monkeypatch.setattr(
        "pvc_migrator.preflight.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout="yes\n", stderr=""),
    )
    checks = run_preflight(
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        required_binaries=("helm", "kubectl", "pv-migrate"),
    )
    assert any(check.status == "blocked" and "pv-migrate" in check.detail for check in checks)


def test_preflight_marks_optional_pod_create_as_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pvc_migrator.preflight.shutil.which", lambda name: "x")

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "create" in command:
            return subprocess.CompletedProcess(command, 0, stdout="no\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="yes\n", stderr="")

    monkeypatch.setattr("pvc_migrator.preflight.subprocess.run", fake_run)
    checks = run_preflight(
        source_cluster=ClusterRef(namespace="src"),
        destination_cluster=ClusterRef(namespace="dst"),
        required_binaries=("helm",),
    )
    assert any(check.status == "warning" and "helper Pods" in check.detail for check in checks)
