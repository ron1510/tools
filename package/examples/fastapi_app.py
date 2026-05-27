"""Demo FastAPI app for the package exception utilities."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Query
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from package import (
    BadRequestError,
    FailedDependencyError,
    NotFoundError,
    OptionalDependencyError,
    optional_import,
)
from package.fastapi import FailedDependency, register_exception_handlers

app = FastAPI(title="Package exception utilities demo")
register_exception_handlers(app)


class ItemPayload(BaseModel):
    name: str = Field(min_length=3)
    quantity: int = Field(gt=0)


@app.get("/")
def endpoint_catalog() -> dict[str, Any]:
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    return {
        "message": "Package exception utilities demo",
        "traceparent": traceparent,
        "endpoints": {
            "bad_request": "/service-error/bad-request",
            "not_found": "/service-error/not-found",
            "failed_dependency": "/service-error/failed-dependency",
            "automatic_dependency_failure": "/depends/failed",
            "missing_optional_import": "/optional-import/missing",
            "validation": "/validation/items/not-an-int?limit=0",
            "trace": "/trace",
        },
        "examples": [
            "curl http://127.0.0.1:8000/service-error/bad-request",
            f"curl -H \"traceparent: {traceparent}\" http://127.0.0.1:8000/trace",
            "curl -X POST http://127.0.0.1:8000/validation/items/1 -H \"content-type: application/json\" -d \"{\\\"name\\\":\\\"ab\\\",\\\"quantity\\\":0}\"",
        ],
    }


@app.get("/service-error/bad-request")
def bad_request() -> None:
    raise BadRequestError("The request cannot be processed")


@app.get("/service-error/not-found")
def not_found() -> None:
    raise NotFoundError("The requested demo resource was not found")


@app.get("/service-error/failed-dependency")
def failed_dependency() -> None:
    raise FailedDependencyError(
        "Database connection is unavailable",
        details={"dependency": "postgres"},
    )


def connect_to_database() -> None:
    raise RuntimeError("connection refused")


@app.get("/depends/failed")
def depends_failed(_: None = FailedDependency(connect_to_database)) -> list[str]:
    return []


@app.get("/optional-import/missing")
def missing_optional_import() -> None:
    try:
        optional_import(
            "definitely_missing_demo_dependency",
            feature="the optional import demo route",
            install_hint="pip install definitely-missing-demo-dependency",
        )
    except OptionalDependencyError as exc:
        raise FailedDependencyError(
            "An optional dependency is missing",
            details={
                "dependency": exc.dependency,
                "feature": exc.feature,
                "install_hint": exc.install_hint,
            },
        ) from exc


@app.post("/validation/items/{item_id}")
def validate_item(
    item_id: int,
    limit: int = Query(gt=0),
    payload: ItemPayload = Body(),
) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "limit": limit,
        "payload": _model_dump(payload),
    }


@app.get("/trace")
def trace_demo() -> None:
    raise BadRequestError("Send a traceparent header to see trace_id in this response")


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
