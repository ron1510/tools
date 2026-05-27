"""FastAPI exception handlers for package service errors."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from inspect import iscoroutinefunction, signature
import re
from typing import Any, TypeVar, cast

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.params import Depends as DependsParam
from fastapi.responses import JSONResponse

from package.exceptions import FailedDependencyError, ServiceError

DependencyCallable = TypeVar("DependencyCallable", bound=Callable[..., Any])
TRACEPARENT_PATTERN = re.compile(
    r"^[\da-f]{2}-(?P<trace_id>[\da-f]{32})-[\da-f]{16}-[\da-f]{2}$",
    re.IGNORECASE,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register package service exception handlers on a FastAPI app."""

    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)


async def service_error_handler(_request: Request, exc: ServiceError) -> JSONResponse:
    """Convert a service error into a JSON HTTP response."""

    content = exc.to_response_body(trace_id=_extract_trace_id(_request))

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert FastAPI request validation errors into the package response shape."""

    content: dict[str, Any] = {
        "detail": "Request validation failed",
        "error_code": "validation_error",
        "details": {
            "errors": jsonable_encoder(exc.errors()),
        },
    }
    trace_id = _extract_trace_id(request)

    if trace_id:
        content["trace_id"] = trace_id

    return JSONResponse(status_code=422, content=content)


def FailedDependency(
    dependency: DependencyCallable,
    *,
    use_cache: bool = True,
    message: str = "A request dependency failed",
) -> DependsParam:
    """Return a FastAPI dependency that maps ordinary failures to HTTP 424."""

    return Depends(
        _wrap_failed_dependency(dependency, message=message),
        use_cache=use_cache,
    )


def _wrap_failed_dependency(
    dependency: DependencyCallable,
    *,
    message: str,
) -> DependencyCallable:
    dependency_name = getattr(dependency, "__name__", dependency.__class__.__name__)

    if iscoroutinefunction(dependency):

        @wraps(dependency)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await dependency(*args, **kwargs)
            except (ServiceError, HTTPException):
                raise
            except Exception as exc:
                raise _dependency_error(message, dependency_name, exc) from exc

        async_wrapper.__signature__ = signature(dependency)  # type: ignore[attr-defined]
        return cast(DependencyCallable, async_wrapper)

    @wraps(dependency)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return dependency(*args, **kwargs)
        except (ServiceError, HTTPException):
            raise
        except Exception as exc:
            raise _dependency_error(message, dependency_name, exc) from exc

    sync_wrapper.__signature__ = signature(dependency)  # type: ignore[attr-defined]
    return cast(DependencyCallable, sync_wrapper)


def _dependency_error(message: str, dependency_name: str, exc: Exception) -> FailedDependencyError:
    return FailedDependencyError(
        message,
        details={
            "dependency": dependency_name,
            "error_type": exc.__class__.__name__,
        },
    )


def _extract_trace_id(request: Request) -> str | None:
    traceparent = request.headers.get("traceparent")

    if not traceparent:
        return None

    match = TRACEPARENT_PATTERN.match(traceparent.strip())

    if not match:
        return None

    trace_id = match.group("trace_id").lower()

    if trace_id == "0" * 32:
        return None

    return trace_id
