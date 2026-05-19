from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.metrics import Observation

from fastapi_demo_service.app_state import DemoServiceAppState


def register_demo_metrics(state: DemoServiceAppState) -> None:
    meter = metrics.get_meter("fastapi_demo_service", "internal")

    meter.create_observable_gauge(
        "fastapi_demo_bootstrap_complete",
        callbacks=[lambda _opts: [Observation(1 if state.ready() else 0, {})]],
        description="1 when the demo FastAPI app has completed bootstrap",
        unit="1",
    )
    meter.create_observable_gauge(
        "fastapi_demo_ticks_total",
        callbacks=[lambda _opts: [Observation(state.ticks_total, {})]],
        description="Total number of demo ticks executed.",
        unit="1",
    )
    meter.create_observable_gauge(
        "fastapi_demo_database_ticks",
        callbacks=[lambda _opts: [Observation(state._database_tick_count(), {})]],
        description="Rows written to the demo in-memory database.",
        unit="1",
    )
