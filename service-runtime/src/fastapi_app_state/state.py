from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import Request


ResourceCloser = Callable[[], Any]


@dataclass(slots=True)
class FastAPIAppState:
    service_name: str
    service_namespace: str
    deployment_environment: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    bootstrapped_at: datetime | None = None
    ready: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    _resource_order: list[str] = field(default_factory=list, repr=False)
    _closers: dict[str, ResourceCloser] = field(default_factory=dict, repr=False)
    background_tasks: list[asyncio.Task[Any]] = field(default_factory=list, repr=False)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    def register_resource(
        self,
        name: str,
        resource: Any,
        closer: ResourceCloser | None = None,
    ) -> None:
        self.resources[name] = resource
        if name not in self._resource_order:
            self._resource_order.append(name)
        if closer is None:
            closer = _infer_closer(resource)
        if closer is not None:
            self._closers[name] = closer

    def get_resource(self, name: str, default: Any = None) -> Any:
        return self.resources.get(name, default)

    def register_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def mark_ready(self) -> None:
        self.ready = True
        self.bootstrapped_at = datetime.now(timezone.utc)

    def mark_not_ready(self) -> None:
        self.ready = False

    def start_background_task(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task: asyncio.Task[Any] = asyncio.create_task(coro)
        self.background_tasks.append(task)
        return task

    async def aclose(self) -> None:
        self.mark_not_ready()
        self.stop_event.set()
        await self._cancel_background_tasks()
        await self._close_resources()

    async def _cancel_background_tasks(self) -> None:
        if not self.background_tasks:
            return
        for task in self.background_tasks:
            task.cancel()
        results = await asyncio.gather(*self.background_tasks, return_exceptions=True)
        del results
        self.background_tasks.clear()

    async def _close_resources(self) -> None:
        for name in reversed(self._resource_order):
            closer = self._closers.get(name)
            if closer is None:
                continue
            result = closer()
            if inspect.isawaitable(result):
                await cast(Awaitable[Any], result)
        self._closers.clear()
        self._resource_order.clear()

    def summary(self) -> dict[str, Any]:
        return {
            "service_name": self.service_name,
            "service_namespace": self.service_namespace,
            "deployment_environment": self.deployment_environment,
            "ready": self.ready,
            "resource_count": len(self.resources),
            "resource_names": tuple(self.resources.keys()),
            "task_count": len(self.background_tasks),
            "started_at": self.started_at.isoformat(),
            "bootstrapped_at": self.bootstrapped_at.isoformat() if self.bootstrapped_at else None,
            "metadata": dict(self.metadata),
        }


def set_app_state(request_or_app: Request | Any, state: FastAPIAppState) -> None:
    app = getattr(request_or_app, "app", request_or_app)
    setattr(app.state, "app_state", state)


def get_app_state(request: Request) -> FastAPIAppState:
    state = getattr(request.app.state, "app_state", None)
    if not isinstance(state, FastAPIAppState):
        raise RuntimeError("FastAPI app state has not been initialized")
    return state


def _infer_closer(resource: Any) -> ResourceCloser | None:
    closer = getattr(resource, "close", None)
    if callable(closer):
        return closer
    closer = getattr(resource, "aclose", None)
    if callable(closer):
        return closer
    return None
