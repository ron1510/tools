from __future__ import annotations

from pvc_migrator.models import CommandExecutionRecord
from pvc_migrator.runlog import RunLogStore


def test_runlog_store_appends_and_loads(tmp_path: str) -> None:
    store = RunLogStore(root=tmp_path)
    run_log = store.append_record(
        "run123",
        "src->dst",
        CommandExecutionRecord(
            workload_name="db",
            command="pv-migrate migrate",
            description="copy",
            status="completed",
        ),
    )
    assert run_log.records[0].status == "completed"
    loaded = store.load("run123")
    assert loaded.records[0].command == "pv-migrate migrate"


def test_runlog_store_reports_completed_commands(tmp_path: str) -> None:
    store = RunLogStore(root=tmp_path)
    store.append_record(
        "run123",
        "src->dst",
        CommandExecutionRecord(
            workload_name="db",
            command="one",
            description="copy",
            status="completed",
        ),
    )
    store.append_record(
        "run123",
        "src->dst",
        CommandExecutionRecord(
            workload_name="db",
            command="two",
            description="copy",
            status="failed",
        ),
    )
    assert store.completed_commands("run123") == {"one"}
