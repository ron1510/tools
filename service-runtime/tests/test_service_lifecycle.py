from __future__ import annotations

from fastapi import FastAPI
from fastapi import Request
from fastapi.testclient import TestClient

from fastapi_app_state import FastAPIAppState, get_app_state
from fastapi_lifespan import build_lifespan
from fastapi_settings import BaseFastAPISettings


def test_lifespan_builds_state_and_runs_hooks() -> None:
    settings = BaseFastAPISettings.model_validate(
        {
            "service_name": "demo",
            "service_namespace": "platform",
        }
    )
    events: list[str] = []
    runtime_state = FastAPIAppState(
        service_name="demo",
        service_namespace="platform",
        deployment_environment="test",
    )

    async def startup(app: FastAPI, state: FastAPIAppState) -> None:
        events.append("startup")
        state.register_metadata("hook", "ran")

    async def shutdown(app: FastAPI, state: FastAPIAppState) -> None:
        events.append("shutdown")
        assert state.ready is False

    app = FastAPI(
        lifespan=build_lifespan(
            settings,
            lambda _cfg: runtime_state,
            startup_hooks=(startup,),
            shutdown_hooks=(shutdown,),
        )
    )
    async def state_route(request: Request) -> dict[str, object]:
        return get_app_state(request).summary()

    app.add_api_route("/state", state_route, methods=["GET"])

    with TestClient(app) as client:
        payload = client.get("/state").json()
        assert payload["ready"] is True
        assert payload["metadata"]["hook"] == "ran"

    assert events == ["startup", "shutdown"]
    assert runtime_state.stop_event.is_set() is True
