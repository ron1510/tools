from __future__ import annotations

from pathlib import Path
from typing import Any

from mongodb_migrator.cli import main


class EndToEndServiceSpy:
    def __init__(self) -> None:
        self.copy_calls: list[Any] = []

    def run_copy(self, request: Any) -> str:
        self.copy_calls.append(request)
        return "users: copied 2 document(s), 1 recreated index(es)\nverification: passed\n"


def test_copy_command_writes_operator_report(monkeypatch: Any, tmp_path: Path) -> None:
    output_path = tmp_path / "report.txt"
    service = EndToEndServiceSpy()
    monkeypatch.setattr("mongodb_migrator.cli.MongoMigrationService", lambda: service)

    exit_code = main(
        [
            "--log-level",
            "ERROR",
            "copy",
            "--source-uri",
            "mongodb://src-router:27017",
            "--source-database",
            "app-source",
            "--target-uri",
            "mongodb://dst-router:27017",
            "--target-database",
            "app-target",
            "--replace-target",
            "--verify",
            "--batch-size",
            "500",
            "--output-file",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert service.copy_calls[0].execution.batch_size == 500
    assert service.copy_calls[0].execution.replace_target is True
    assert output_path.read_text(encoding="utf-8").endswith("verification: passed\n")
