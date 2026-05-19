from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from pvc_migrator.models import ChartInput, ClusterRef, PlanRequest
from pvc_migrator.service import MigrationPlannerService


def _kind_ready() -> bool:
    return shutil.which("kind") is not None and shutil.which("kubectl") is not None and shutil.which("helm") is not None


@pytest.mark.e2e
def test_kind_smoke_plan_builds_against_real_cluster() -> None:
    if not _kind_ready():
        pytest.skip("kind/helm/kubectl not available")
    current_context = subprocess.run(
        ["kubectl", "config", "current-context"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not current_context:
        pytest.skip("no current kubectl context")

    fixtures = Path(__file__).parent / "fixtures" / "kind-smoke"
    suffix = uuid.uuid4().hex[:6]
    src_ns = f"pvc-migrator-src-{suffix}"
    dst_ns = f"pvc-migrator-dst-{suffix}"
    namespace_yaml = (fixtures / "namespace.yaml").read_text(encoding="utf-8")
    pvc_yaml = (fixtures / "pvcs.yaml").read_text(encoding="utf-8")
    namespace_yaml = namespace_yaml.replace("pvc-migrator-src", src_ns).replace("pvc-migrator-dst", dst_ns)
    pvc_yaml = pvc_yaml.replace("pvc-migrator-src", src_ns).replace("pvc-migrator-dst", dst_ns)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        namespace_file = temp_path / "namespace.yaml"
        pvc_file = temp_path / "pvcs.yaml"
        namespace_file.write_text(namespace_yaml, encoding="utf-8")
        pvc_file.write_text(pvc_yaml, encoding="utf-8")

        try:
            subprocess.run(["kubectl", "apply", "--server-side", "-f", str(namespace_file)], check=True)
            subprocess.run(["kubectl", "apply", "-f", str(pvc_file)], check=True)

            chart_dir = Path(__file__).parent / "fixtures" / "charts" / "basic-migrator-app"
            service = MigrationPlannerService()
            plan = service.build_plan(
                PlanRequest(
                    source=ChartInput(
                        chart=str(chart_dir),
                        values_file=str(chart_dir / "values-source.yaml"),
                        release_name="source-app",
                    ),
                    destination=ChartInput(
                        chart=str(chart_dir),
                        values_file=str(chart_dir / "values-dest.yaml"),
                        release_name="dest-app",
                    ),
                    source_cluster=ClusterRef(namespace=src_ns, context=current_context),
                    destination_cluster=ClusterRef(namespace=dst_ns, context=current_context),
                )
            )
            assert plan.workload_plans
            assert any(workload.engine == "pv-migrate" for workload in plan.workload_plans)
        finally:
            subprocess.run(
                ["kubectl", "delete", "ns", src_ns, dst_ns, "--ignore-not-found=true", "--wait=true"],
                check=True,
            )
