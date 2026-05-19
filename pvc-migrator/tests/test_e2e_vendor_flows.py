from __future__ import annotations

from contextlib import contextmanager
import shutil
import socket
import subprocess
import time
from pathlib import Path
import uuid
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import pytest

from pvc_migrator.models import ChartInput, ClusterRef, PlanRequest
from pvc_migrator.service import MigrationPlannerService


def _vendor_tools_ready() -> bool:
    return all(shutil.which(binary) is not None for binary in ("kind", "helm", "kubectl"))


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), check=True, capture_output=True, text=True)


def _run_no_capture(*args: str) -> None:
    subprocess.run(list(args), check=True)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _port_forward(namespace: str, service: str, local_port: int, remote_port: int) -> object:
    process = subprocess.Popen(
        [
            "kubectl",
            "-n",
            namespace,
            "port-forward",
            f"svc/{service}",
            f"{local_port}:{remote_port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            with socket.socket() as sock:
                if sock.connect_ex(("127.0.0.1", local_port)) == 0:
                    break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"port-forward for {service} did not become ready")
        yield
    finally:
        process.terminate()
        process.wait(timeout=20)


def _http_post(url: str, body: bytes) -> str:
    request = Request(url, data=body, method="POST", headers={"Content-Type": "text/plain"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _http_get(url: str) -> str:
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def _wait_for_substring(url: str, needle: str, *, timeout_seconds: int = 60) -> str:
    deadline = time.time() + timeout_seconds
    last_response = ""
    while time.time() < deadline:
        last_response = _http_get(url)
        if needle in last_response:
            return last_response
        time.sleep(2)
    raise AssertionError(f"{needle!r} not found in response within {timeout_seconds}s: {last_response}")


@pytest.mark.e2e
def test_vendor_specific_real_flows() -> None:
    if not _vendor_tools_ready():
        pytest.skip("kind/helm/kubectl not available")

    current_context = _run("kubectl", "config", "current-context").stdout.strip()
    if not current_context:
        pytest.skip("no current kubectl context")

    chart_dir = Path(__file__).parent / "fixtures" / "charts" / "vendor-migrator-app"
    suffix = uuid.uuid4().hex[:6]
    src_ns = f"vendor-flow-src-{suffix}"
    dst_ns = f"vendor-flow-dst-{suffix}"

    _run_no_capture("kubectl", "create", "ns", src_ns)
    _run_no_capture("kubectl", "create", "ns", dst_ns)

    try:
        _run_no_capture(
            "helm",
            "upgrade",
            "--install",
            "vendor-source",
            str(chart_dir),
            "-f",
            str(chart_dir / "values-source.yaml"),
            "-n",
            src_ns,
        )
        _run_no_capture(
            "helm",
            "upgrade",
            "--install",
            "vendor-dest",
            str(chart_dir),
            "-f",
            str(chart_dir / "values-dest.yaml"),
            "-n",
            dst_ns,
        )

        _run_no_capture("kubectl", "-n", src_ns, "rollout", "status", "deployment/source-arangodb", "--timeout=240s")
        _run_no_capture("kubectl", "-n", dst_ns, "rollout", "status", "deployment/dest-arangodb", "--timeout=240s")
        _run_no_capture("kubectl", "-n", src_ns, "rollout", "status", "statefulset/source-vmstorage", "--timeout=240s")
        _run_no_capture("kubectl", "-n", dst_ns, "rollout", "status", "statefulset/dest-vmstorage", "--timeout=240s")
        _run_no_capture("kubectl", "-n", src_ns, "rollout", "status", "deployment/source-vminsert", "--timeout=240s")
        _run_no_capture("kubectl", "-n", src_ns, "rollout", "status", "deployment/source-vmselect", "--timeout=240s")
        _run_no_capture("kubectl", "-n", dst_ns, "rollout", "status", "deployment/dest-vminsert", "--timeout=240s")
        _run_no_capture("kubectl", "-n", dst_ns, "rollout", "status", "deployment/dest-vmselect", "--timeout=240s")

        _run_no_capture(
            "kubectl",
            "-n",
            src_ns,
            "exec",
            "deployment/source-arangodb",
            "--",
            "arangosh",
            "--server.authentication=false",
            "--javascript.execute-string",
            (
                "db._databases().indexOf('testdb') === -1 && db._createDatabase('testdb'); "
                "db._useDatabase('testdb'); "
                "db._collection('items') || db._create('items'); "
                "try { db.items.remove('hello'); } catch (e) {} "
                "db.items.insert({_key:'hello', value:'world'});"
            ),
        )

        _run_no_capture(
            "kubectl",
            "-n",
            src_ns,
            "exec",
            "statefulset/source-vmstorage",
            "--",
            "sh",
            "-lc",
            "echo vm-sentinel > /vmstorage-data/pvc-migrator-sentinel.txt",
        )

        source_insert_port = _free_port()
        source_query_port = _free_port()
        with _port_forward(src_ns, "source-vminsert", source_insert_port, 8480), _port_forward(
            src_ns, "source-vmselect", source_query_port, 8481
        ):
            _http_post(
                f"http://127.0.0.1:{source_insert_port}/insert/0/prometheus/api/v1/import/prometheus",
                b'pvc_migrator_vendor_metric{job="e2e"} 42\n',
            )
            source_query = _wait_for_substring(
                f"http://127.0.0.1:{source_query_port}/select/0/prometheus/api/v1/query?query="
                f"{quote_plus('pvc_migrator_vendor_metric')}",
                "pvc_migrator_vendor_metric",
                timeout_seconds=70,
            )
            assert '"42"' in source_query or '"42.000000"' in source_query

        service = MigrationPlannerService()
        plan = service.build_plan(
            PlanRequest(
                source=ChartInput(
                    chart=str(chart_dir),
                    values_file=str(chart_dir / "values-source.yaml"),
                    release_name="vendor-source",
                ),
                destination=ChartInput(
                    chart=str(chart_dir),
                    values_file=str(chart_dir / "values-dest.yaml"),
                    release_name="vendor-dest",
                ),
                    source_cluster=ClusterRef(namespace=src_ns, context=current_context),
                    destination_cluster=ClusterRef(namespace=dst_ns, context=current_context),
                    include_workloads=(
                        "arangodb-single",
                        "victoriametrics-vmstorage",
                        "victoriametrics-aux",
                    ),
                )
            )

        plans_by_engine = {workload.engine for workload in plan.workload_plans}
        assert "arangodb-native" in plans_by_engine
        assert "victoriametrics-vmstorage" in plans_by_engine
        assert "victoriametrics-aux-skip" in plans_by_engine

        arango_workload = next(
            workload.workload_name for workload in plan.workload_plans if workload.engine == "arangodb-native"
        )
        vmstorage_workload = next(
            workload.workload_name for workload in plan.workload_plans if workload.engine == "victoriametrics-vmstorage"
        )
        service.execute_plan(
            plan,
            approved=True,
            selected_workloads=(arango_workload, vmstorage_workload),
        )

        result = _run(
            "kubectl",
            "-n",
            dst_ns,
            "exec",
            "deployment/dest-arangodb",
            "--",
            "arangosh",
            "--server.authentication=false",
            "--javascript.execute-string",
            "db._useDatabase('testdb'); print(JSON.stringify(db.items.document('hello')));",
        )
        assert '"value":"world"' in result.stdout

        assert Path(".pvc-migrator-runs/source-vmstorage-vmbackup-latest.tar").exists()
        _run_no_capture("kubectl", "-n", dst_ns, "rollout", "status", "statefulset/dest-vmstorage", "--timeout=240s")

        destination_query_port = _free_port()
        with _port_forward(dst_ns, "dest-vmselect", destination_query_port, 8481):
            destination_query = _wait_for_substring(
                f"http://127.0.0.1:{destination_query_port}/select/0/prometheus/api/v1/query?query="
                f"{quote_plus('pvc_migrator_vendor_metric')}",
                "pvc_migrator_vendor_metric",
                timeout_seconds=70,
            )
            assert '"42"' in destination_query or '"42.000000"' in destination_query
    finally:
        _run_no_capture("kubectl", "delete", "ns", src_ns, dst_ns, "--ignore-not-found=true", "--wait=true")
