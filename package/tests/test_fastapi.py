from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from package import BadRequestError, FailedDependencyError
from package.fastapi import FailedDependency, register_exception_handlers


class ItemPayloadModel(BaseModel):
    name: str = Field(min_length=3)


def test_failed_dependency_error_maps_to_424() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    def require_database() -> None:
        raise FailedDependencyError(
            "Database connection is unavailable",
            details={"dependency": "postgres"},
        )

    @app.get("/items")
    def list_items(_: None = Depends(require_database)) -> list[str]:
        return []

    response = TestClient(app).get("/items")

    assert response.status_code == 424
    assert response.json() == {
        "detail": "Database connection is unavailable",
        "error_code": "failed_dependency",
        "details": {"dependency": "postgres"},
    }


def test_service_error_handler_uses_class_defaults_without_details() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items")
    def list_items() -> list[str]:
        raise BadRequestError("Invalid query")

    response = TestClient(app).get("/items")

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid query",
        "error_code": "bad_request",
    }


def test_failed_dependency_wraps_sync_dependency_exception_as_424() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    def load_database() -> None:
        raise RuntimeError("connection refused")

    @app.get("/items")
    def list_items(_: None = FailedDependency(load_database)) -> list[str]:
        return []

    response = TestClient(app).get("/items")

    assert response.status_code == 424
    assert response.json() == {
        "detail": "A request dependency failed",
        "error_code": "failed_dependency",
        "details": {
            "dependency": "load_database",
            "error_type": "RuntimeError",
        },
    }


def test_failed_dependency_wraps_async_dependency_exception_as_424() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    async def load_database() -> None:
        raise RuntimeError("connection refused")

    @app.get("/items")
    def list_items(_: None = FailedDependency(load_database)) -> list[str]:
        return []

    response = TestClient(app).get("/items")

    assert response.status_code == 424
    assert response.json() == {
        "detail": "A request dependency failed",
        "error_code": "failed_dependency",
        "details": {
            "dependency": "load_database",
            "error_type": "RuntimeError",
        },
    }


def test_failed_dependency_preserves_explicit_failed_dependency_error() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    def load_database() -> None:
        raise FailedDependencyError(
            "Database unavailable",
            details={"dependency": "postgres"},
        )

    @app.get("/items")
    def list_items(_: None = FailedDependency(load_database)) -> list[str]:
        return []

    response = TestClient(app).get("/items")

    assert response.status_code == 424
    assert response.json() == {
        "detail": "Database unavailable",
        "error_code": "failed_dependency",
        "details": {"dependency": "postgres"},
    }


def test_failed_dependency_preserves_http_exception() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    def require_auth() -> None:
        raise HTTPException(status_code=401, detail="Missing token")

    @app.get("/items")
    def list_items(_: None = FailedDependency(require_auth)) -> list[str]:
        return []

    response = TestClient(app).get("/items")

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing token"}


def test_failed_dependency_preserves_dependency_parameters() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    def load_database(item_id: int) -> int:
        if item_id == 0:
            raise RuntimeError("missing item")
        return item_id

    @app.get("/items/{item_id}")
    def get_item(item_id: int = FailedDependency(load_database)) -> dict[str, int]:
        return {"item_id": item_id}

    client = TestClient(app)

    assert client.get("/items/7").json() == {"item_id": 7}
    assert client.get("/items/0").status_code == 424


def test_service_error_response_includes_trace_id_from_traceparent() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items")
    def list_items() -> list[str]:
        raise BadRequestError("Invalid query")

    response = TestClient(app).get(
        "/items",
        headers={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid query",
        "error_code": "bad_request",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    }


def test_service_error_response_uses_error_trace_id_without_traceparent() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items")
    def list_items() -> list[str]:
        raise BadRequestError(
            "Invalid query",
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        )

    response = TestClient(app).get("/items")

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid query",
        "error_code": "bad_request",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    }


def test_service_error_response_omits_invalid_traceparent() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items")
    def list_items() -> list[str]:
        raise BadRequestError("Invalid query")

    response = TestClient(app).get(
        "/items",
        headers={"traceparent": "invalid"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid query",
        "error_code": "bad_request",
    }


def test_service_error_response_omits_missing_traceparent() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items")
    def list_items() -> list[str]:
        raise BadRequestError("Invalid query")

    response = TestClient(app).get("/items")

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid query",
        "error_code": "bad_request",
    }


def test_service_error_response_keeps_details_with_trace_id() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items")
    def list_items() -> list[str]:
        raise FailedDependencyError(
            "Database unavailable",
            details={"dependency": "postgres"},
        )

    response = TestClient(app).get(
        "/items",
        headers={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
    )

    assert response.status_code == 424
    assert response.json() == {
        "detail": "Database unavailable",
        "error_code": "failed_dependency",
        "details": {"dependency": "postgres"},
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    }


def test_failed_dependency_response_includes_trace_id() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    def load_database() -> None:
        raise RuntimeError("connection refused")

    @app.get("/items")
    def list_items(_: None = FailedDependency(load_database)) -> list[str]:
        return []

    response = TestClient(app).get(
        "/items",
        headers={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
    )

    assert response.status_code == 424
    assert response.json() == {
        "detail": "A request dependency failed",
        "error_code": "failed_dependency",
        "details": {
            "dependency": "load_database",
            "error_type": "RuntimeError",
        },
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    }


def test_validation_error_is_normalized() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/items/{item_id}")
    def create_item(item_id: int, payload: ItemPayloadModel) -> dict[str, object]:
        return {"item_id": item_id, "payload": payload.model_dump()}

    response = TestClient(app).post("/items/not-an-int", json={"name": "ab"})

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Request validation failed"
    assert body["error_code"] == "validation_error"
    assert "errors" in body["details"]
    assert "trace_id" not in body


def test_validation_error_includes_trace_id() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/items/{item_id}")
    def get_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    response = TestClient(app).get(
        "/items/not-an-int",
        headers={"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
    )

    assert response.status_code == 422
    assert response.json()["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
