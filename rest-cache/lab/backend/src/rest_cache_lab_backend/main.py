from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)


class CreateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


Store = dict[str, dict[str, dict[str, str]]]

INITIAL_STORE: Store = {
    "resources": {
        "123": {"id": "123", "name": "resource-123"},
        "456": {"id": "456", "name": "resource-456"},
    },
    "users": {
        "1": {"id": "1", "name": "user-1"},
        "2": {"id": "2", "name": "user-2"},
    },
    "permissions": {
        "read": {"id": "read", "name": "read"},
        "write": {"id": "write", "name": "write"},
    },
}


def create_app() -> FastAPI:
    app = FastAPI(title="REST Cache Lab Backend")
    lock = Lock()
    store = deepcopy(INITIAL_STORE)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/errors/{status_code}")
    def error(status_code: int) -> Response:
        return Response(f"lab error {status_code}\n", status_code=status_code)

    @app.get("/api/v1/cookie")
    def cookie(response: Response) -> dict[str, str]:
        response.set_cookie("lab", "not-cacheable")
        return {"status": "cookie"}

    @app.get("/api/v1/{family}")
    def list_items(family: str) -> dict[str, Any]:
        with lock:
            family_store = get_family_store(store, family)
            return {"family": family, "items": list(family_store.values())}

    @app.get("/api/v1/{family}/search")
    def search_items(family: str, q: str = Query(default="")) -> dict[str, Any]:
        with lock:
            family_store = get_family_store(store, family)
            matches = [item for item in family_store.values() if q.lower() in item["name"].lower()]
            return {"family": family, "query": q, "items": matches}

    @app.get("/api/v1/{family}/{item_id}")
    def get_item(family: str, item_id: str) -> dict[str, str]:
        with lock:
            family_store = get_family_store(store, family)
            if item_id not in family_store:
                raise HTTPException(status_code=404, detail="item not found")
            return family_store[item_id]

    @app.post("/api/v1/{family}", status_code=201)
    def create_item(family: str, payload: CreateItem) -> dict[str, str]:
        with lock:
            family_store = store.setdefault(family, {})
            family_store[payload.id] = {"id": payload.id, "name": payload.name}
            return family_store[payload.id]

    @app.put("/api/v1/{family}/{item_id}")
    def replace_item(family: str, item_id: str, payload: ItemUpdate) -> dict[str, str]:
        return upsert_item(store, lock, family, item_id, payload.name)

    @app.patch("/api/v1/{family}/{item_id}")
    def patch_item(family: str, item_id: str, payload: ItemUpdate) -> dict[str, str]:
        return upsert_item(store, lock, family, item_id, payload.name)

    @app.delete("/api/v1/{family}/{item_id}", status_code=204)
    def delete_item(family: str, item_id: str) -> Response:
        with lock:
            family_store = get_family_store(store, family)
            family_store.pop(item_id, None)
        return Response(status_code=204)

    return app


def get_family_store(store: Store, family: str) -> dict[str, dict[str, str]]:
    if family not in store:
        raise HTTPException(status_code=404, detail="family not found")
    return store[family]


def upsert_item(store: Store, lock: Lock, family: str, item_id: str, name: str) -> dict[str, str]:
    with lock:
        family_store = store.setdefault(family, {})
        family_store[item_id] = {"id": item_id, "name": name}
        return family_store[item_id]


app = create_app()


def main() -> None:
    uvicorn.run("rest_cache_lab_backend.main:app", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
