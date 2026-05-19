from __future__ import annotations

import time
from typing import Any, cast

from fastapi.testclient import TestClient

from fastapi_demo_service.app import create_app
from fastapi_demo_service.settings import DemoFastAPISettings


def test_fastapi_demo_app_updates_state_and_exposes_stats(monkeypatch) -> None:
    monkeypatch.setenv("SERVICE_NAME", "demo-api")
    monkeypatch.setenv("OTEL_METRICS_ENABLED", "false")
    settings = DemoFastAPISettings.from_env()
    app = create_app(settings)

    with TestClient(app) as client:
        deadline = time.time() + 5
        stats_payload: dict[str, object] = {}
        ready_payload: dict[str, object] = {}
        while time.time() < deadline:
            ready_payload = client.get("/readyz").json()
            stats_payload = client.get("/demo/state").json()
            if _as_bool(ready_payload["ready"]) and _as_int(stats_payload["ticks_total"]) > 0:
                break
            time.sleep(0.05)

        assert _as_bool(ready_payload["ready"]) is True
        assert _as_int(stats_payload["ticks_total"]) > 0
        assert _as_int(client.get("/demo/database-count").json()["database_ticks"]) > 0
        assert _as_bool(client.get("/stats").json()["ready"]) is True


def _as_int(value: object) -> int:
    return int(cast(Any, value))


def _as_bool(value: object) -> bool:
    return bool(cast(Any, value))
