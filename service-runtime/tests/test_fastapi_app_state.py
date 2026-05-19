from __future__ import annotations

from fastapi_app_state import FastAPIAppState


class ClosableResource:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_fastapi_app_state_registers_resources_and_closes_them() -> None:
    state = FastAPIAppState(
        service_name="demo",
        service_namespace="platform",
        deployment_environment="test",
    )
    resource = ClosableResource()

    state.register_resource("db", resource)
    state.mark_ready()

    summary = state.summary()
    assert summary["ready"] is True
    assert summary["resource_names"] == ("db",)

    import asyncio

    asyncio.run(state.aclose())

    assert resource.closed is True
    assert state.stop_event.is_set() is True
