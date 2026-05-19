from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_app_state import FastAPIAppState, set_app_state
from fastapi_health import build_health_router


def test_health_router_reports_live_ready_and_stats() -> None:
    app = FastAPI()
    state = FastAPIAppState(
        service_name="demo",
        service_namespace="default",
        deployment_environment="test",
    )
    state.mark_ready()
    state.register_metadata("ticks", 3)
    set_app_state(app, state)
    app.include_router(build_health_router())

    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/livez").json() == {"status": "ok"}
        assert client.get("/readyz").json() == {"ready": True, "resource_count": 0}
        stats = client.get("/stats").json()
        assert stats["ready"] is True
        assert stats["metadata"] == {"ticks": 3}
