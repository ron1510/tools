from __future__ import annotations

from fastapi import APIRouter, Depends

from fastapi_app_state import FastAPIAppState, get_app_state


def build_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/readyz")
    async def readyz(state: FastAPIAppState = Depends(get_app_state)) -> dict[str, object]:
        return {"ready": state.ready, "resource_count": len(state.resources)}

    @router.get("/stats")
    async def stats(state: FastAPIAppState = Depends(get_app_state)) -> dict[str, object]:
        return state.summary()

    return router
