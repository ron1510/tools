from __future__ import annotations

from pathlib import Path
from typing import Any

from mongodb_migrator.cli import main
class ServiceSpy:
    def __init__(self) -> None:
        self.copy_requests: list[Any] = []
        self.loaded_paths: list[str] = []

    def run_copy(self, request: Any) -> str:
        self.copy_requests.append(request)
        return "users: copied 2 document(s), 1 recreated index(es)\n"

    def load_job(self, path: str) -> dict[str, str]:
        self.loaded_paths.append(path)
        return {"path": path}

    def inspect_job(self, job: Any) -> str:
        return f"inspect:{job['path']}\n"

    def run_job(self, job: Any) -> str:
        return f"run:{job['path']}\n"


def test_cli_copy_writes_output_file(monkeypatch: Any, tmp_path: Path) -> None:
    output_path = tmp_path / "copy.txt"
    service = ServiceSpy()
    monkeypatch.setattr("mongodb_migrator.cli.MongoMigrationService", lambda: service)

    exit_code = main(
        [
            "--log-level",
            "ERROR",
            "copy",
            "--source-uri",
            "mongodb://src",
            "--source-database",
            "app",
            "--target-uri",
            "mongodb://dst",
            "--target-database",
            "app-copy",
            "--include-collection",
            "users",
            "--verify",
            "--output-file",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert service.copy_requests[0].include_collections == ("users",)
    assert service.copy_requests[0].verification.enabled is True
    assert output_path.read_text(encoding="utf-8").startswith("users:")


def test_cli_inspect_uses_loaded_job(monkeypatch: Any, capsys: Any) -> None:
    service = ServiceSpy()
    monkeypatch.setattr("mongodb_migrator.cli.MongoMigrationService", lambda: service)

    exit_code = main(["--log-level", "ERROR", "inspect", "--config", "job.yaml"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert service.loaded_paths == ["job.yaml"]
    assert captured.out == "inspect:job.yaml\n"
