from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


@pytest.mark.e2e
@pytest.mark.real_mongo
def test_copy_cli_runs_against_real_mongo_and_writes_report(
    real_mongo_endpoints: tuple[str, str],
    tmp_path: Path,
) -> None:
    from pymongo import MongoClient

    source_uri, target_uri = real_mongo_endpoints
    source_client: Any = MongoClient(source_uri)
    target_client: Any = MongoClient(target_uri)

    source_db = source_client["cli_source"]
    target_db = target_client["cli_target"]
    source_db.drop_collection("events")
    target_db.drop_collection("events")
    source_db["events"].insert_many(
        [
            {"_id": 101, "kind": "login"},
            {"_id": 102, "kind": "logout"},
        ]
    )

    output_path = tmp_path / "copy-report.txt"
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src_path if not existing_pythonpath else src_path + os.pathsep + existing_pythonpath
    command = [
        sys.executable,
        "-m",
        "mongodb_migrator",
        "--log-level",
        "ERROR",
        "copy",
        "--source-uri",
        source_uri,
        "--source-database",
        "cli_source",
        "--target-uri",
        target_uri,
        "--target-database",
        "cli_target",
        "--replace-target",
        "--verify",
        "--output-file",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)

    assert completed.returncode == 0, completed.stderr
    assert output_path.exists()
    report = output_path.read_text(encoding="utf-8")
    assert "events: copied 2 document(s)" in report
    assert "verification: passed" in report
    assert target_db["events"].count_documents({}) == 2

    source_client.close()
    target_client.close()
