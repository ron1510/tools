from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

EXAMPLES_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLES_ROOT))

from examples.fastapi_app import app  # noqa: E402


def test_demo_app_root_returns_endpoint_catalog() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Package exception utilities demo"
    assert "endpoints" in body
    assert "automatic_dependency_failure" in body["endpoints"]
