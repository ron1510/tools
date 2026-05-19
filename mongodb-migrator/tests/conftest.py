from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
REAL_COMPOSE_FILE = PROJECT_ROOT / "tests" / "real_mongo_compose.yaml"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_mongo: tests that require Docker and real MongoDB instances",
    )


@pytest.fixture(scope="session")
def real_mongo_endpoints() -> Generator[tuple[str, str], None, None]:
    if os.getenv("MONGODB_MIGRATOR_RUN_REAL_TESTS") != "1":
        pytest.skip("set MONGODB_MIGRATOR_RUN_REAL_TESTS=1 to run real MongoDB tests")
    _ensure_docker_available()
    try:
        import pymongo  # noqa: F401
    except ImportError:
        pytest.skip("pymongo is required for real MongoDB tests")

    _run_compose_command("up", "-d")
    try:
        source_uri = "mongodb://127.0.0.1:37017"
        target_uri = "mongodb://127.0.0.1:37018"
        _wait_for_mongo(source_uri)
        _wait_for_mongo(target_uri)
        yield source_uri, target_uri
    finally:
        _run_compose_command("down", "--volumes", "--remove-orphans")


def _ensure_docker_available() -> None:
    command = ["docker", "version", "--format", "{{.Server.Version}}"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        pytest.skip(f"docker is not available: {completed.stderr.strip() or completed.stdout.strip()}")


def _run_compose_command(*args: str) -> None:
    command = ["docker", "compose", "-f", str(REAL_COMPOSE_FILE), *args]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"docker compose {' '.join(args)} failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )


def _wait_for_mongo(uri: str, timeout_seconds: float = 60.0) -> None:
    from pymongo import MongoClient

    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            client: Any = MongoClient(uri, serverSelectionTimeoutMS=1000)
            client.admin.command("ping")
            client.close()
            return
        except Exception as exc:  # pragma: no cover - depends on runtime
            last_error = str(exc)
            time.sleep(1.0)
    raise RuntimeError(f"timed out waiting for MongoDB at {uri}: {last_error}")
