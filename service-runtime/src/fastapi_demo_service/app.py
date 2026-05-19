from __future__ import annotations

import asyncio

from fastapi import FastAPI, Request

from fastapi_app_state import FastAPIAppState
from fastapi_demo_service.app_state import DemoServiceAppState, build_demo_state
from fastapi_demo_service.metrics import register_demo_metrics
from fastapi_demo_service.settings import DemoFastAPISettings
from fastapi_health import build_health_router
from fastapi_lifespan import build_lifespan
from fastapi_observability import FastAPIMetricsMiddleware, configure_telemetry


def create_app(settings: DemoFastAPISettings | None = None) -> FastAPI:
    settings = settings or DemoFastAPISettings.from_env()
    configure_telemetry(settings, meter_name="fastapi_demo_service")
    demo_state = build_demo_state(
        service_name=settings.service_name,
        service_namespace=settings.service_namespace,
        deployment_environment=settings.deployment_environment,
        ttl_seconds=settings.state_ttl_seconds,
        max_items=settings.max_state_items,
    )

    async def _startup(app: FastAPI, state: FastAPIAppState) -> None:
        app.state.demo_state = demo_state
        register_demo_metrics(demo_state)
        state.start_background_task(_tick_loop(demo_state, settings.tick_interval_seconds))

    lifespan = build_lifespan(settings, lambda _cfg: demo_state.runtime, startup_hooks=(_startup,))

    app = FastAPI(
        title=settings.service_name,
        lifespan=lifespan,
    )
    app.add_middleware(
        FastAPIMetricsMiddleware,
        meter_name="fastapi_demo_service",
        tracer_name="fastapi_demo_service",
    )
    app.include_router(build_health_router())

    @app.get("/demo/database-count")
    async def database_count(request: Request) -> dict[str, int]:
        return {"database_ticks": _get_demo_state(request)._database_tick_count()}

    @app.get("/demo/state")
    async def demo_state_route(request: Request) -> dict[str, object]:
        return _get_demo_state(request).stats()

    return app


async def _tick_loop(state: DemoServiceAppState, interval_seconds: float) -> None:
    while not state.runtime.stop_event.is_set():
        payload = f"tick-{state.ticks_total + 1}"
        state.mark_tick(payload)
        await asyncio.sleep(interval_seconds)


def _get_demo_state(request: Request) -> DemoServiceAppState:
    demo_state = getattr(request.app.state, "demo_state", None)
    if isinstance(demo_state, DemoServiceAppState):
        return demo_state
    raise RuntimeError("demo service state has not been initialized")
