from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeAlias

from fastapi import FastAPI

from fastapi_app_state import FastAPIAppState, set_app_state
from fastapi_settings import BaseFastAPISettings

LifespanHook: TypeAlias = Callable[[FastAPI, FastAPIAppState], Awaitable[None] | None]
StateFactory: TypeAlias = Callable[[BaseFastAPISettings], FastAPIAppState]


def build_lifespan(
    settings: BaseFastAPISettings,
    state_factory: StateFactory,
    startup_hooks: tuple[LifespanHook, ...] = (),
    shutdown_hooks: tuple[LifespanHook, ...] = (),
):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = state_factory(settings)
        set_app_state(app, state)
        app.state.settings = settings
        for hook in startup_hooks:
            await _maybe_await(hook(app, state))
        state.mark_ready()
        try:
            yield
        finally:
            state.mark_not_ready()
            for hook in reversed(shutdown_hooks):
                await _maybe_await(hook(app, state))
            await state.aclose()

    return lifespan


async def _maybe_await(result: Any) -> None:
    if inspect.isawaitable(result):
        await result
