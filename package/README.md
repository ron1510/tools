# Package

Exception handling utilities for Python packages and services.

## Optional imports

Use `optional_import` when a feature depends on an optional dependency and you
want a clear error message when that dependency is not installed.

```python
from package import optional_import

yaml = optional_import(
    "yaml",
    feature="YAML config loading",
    install_hint="pip install PyYAML",
)

data = yaml.safe_load("name: example")
```

If the import fails, `OptionalDependencyError` includes the optional dependency
name, the feature that needs it, the install command, and the original import
error.

## Service errors

`package` includes typed service exceptions with default HTTP status codes and
machine-readable error codes:

- `BadRequestError` -> `400`, `bad_request`
- `UnauthorizedError` -> `401`, `unauthorized`
- `ForbiddenError` -> `403`, `forbidden`
- `NotFoundError` -> `404`, `not_found`
- `ConflictError` -> `409`, `conflict`
- `FailedDependencyError` -> `424`, `failed_dependency`
- `InternalServiceError` -> `500`, `internal_service_error`

```python
from package import FailedDependencyError

raise FailedDependencyError(
    "Database connection is unavailable",
    details={"dependency": "postgres"},
)
```

All service errors accept `message`, optional `details`, optional `trace_id`,
and optional `error_code` or `status_code` overrides.

## FastAPI

Install the FastAPI extra when using service handlers:

```shell
pip install "package[fastapi]"
```

Register the handlers once when creating the app:

```python
from fastapi import Depends, FastAPI
from package import FailedDependencyError
from package.fastapi import FailedDependency, register_exception_handlers

app = FastAPI()
register_exception_handlers(app)


def require_database() -> None:
    raise FailedDependencyError(
        "Database connection is unavailable",
        details={"dependency": "postgres"},
    )


@app.get("/items")
def list_items(_: None = FailedDependency(require_database)) -> list[str]:
    return []
```

The response will use the exception status code and a simple body:

```json
{
  "detail": "Database connection is unavailable",
  "error_code": "failed_dependency",
  "details": {
    "dependency": "postgres"
  }
}
```

If the request contains a valid W3C `traceparent` header, FastAPI error
responses include the trace ID as a top-level field:

```json
{
  "detail": "Database connection is unavailable",
  "error_code": "failed_dependency",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

`424 Failed Dependency` is explicit: raise `FailedDependencyError` from a
dependency or service path when an upstream dependency fails. Use
`FailedDependency(...)` when you want ordinary dependency exceptions to become
`424 Failed Dependency` automatically.

## API reference

### `optional_import(module_name, *, feature=None, install_hint=None, package=None)`

Imports an optional dependency and returns the imported module. Raises
`OptionalDependencyError` if the dependency cannot be imported.

### `PackageError`

Base exception for this package.

### `OptionalDependencyError`

Raised when an optional dependency is missing or cannot be imported.

### `ServiceError`

Base class for service-facing errors. Subclasses provide default `status_code`
and `error_code` values.

### `register_exception_handlers(app)`

Registers FastAPI exception handlers for `ServiceError` subclasses. This is
available from `package.fastapi` and requires the FastAPI extra.

It also normalizes FastAPI request validation errors into the same response
shape:

```json
{
  "detail": "Request validation failed",
  "error_code": "validation_error",
  "details": {
    "errors": []
  }
}
```

## Demo app

Install development dependencies and run the example app:

```shell
cd package
pip install ".[dev]"
cd ..
python -m uvicorn examples.fastapi_app:app --app-dir package --reload
```

Example requests:

```shell
curl http://127.0.0.1:8000/service-error/bad-request
curl http://127.0.0.1:8000/depends/failed
curl -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" http://127.0.0.1:8000/trace
curl -X POST "http://127.0.0.1:8000/validation/items/not-an-int?limit=0" -H "content-type: application/json" -d "{\"name\":\"ab\",\"quantity\":0}"
```
