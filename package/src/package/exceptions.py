"""Typed exceptions for packages and Python services."""

from __future__ import annotations

from typing import Any


class PackageError(Exception):
    """Base exception for this package."""


class OptionalDependencyError(PackageError, ImportError):
    """Raised when an optional dependency cannot be imported."""

    def __init__(
        self,
        dependency: str,
        *,
        feature: str | None = None,
        install_hint: str | None = None,
        original_error: ImportError | None = None,
    ) -> None:
        self.dependency = dependency
        self.feature = feature
        self.install_hint = install_hint
        self.original_error = original_error

        message_parts = [f"Optional dependency '{dependency}' could not be imported."]

        if feature:
            message_parts.append(f"It is required for {feature}.")

        if install_hint:
            message_parts.append(f"Install it with: {install_hint}")
        else:
            top_level_name = dependency.split(".", 1)[0]
            message_parts.append(f"Install the missing dependency, for example: pip install {top_level_name}")

        if original_error:
            message_parts.append(f"Original error: {original_error}")

        super().__init__(" ".join(message_parts))


class ServiceError(PackageError):
    """Base class for service-facing errors."""

    status_code = 500
    error_code = "service_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.trace_id = trace_id
        self.error_code = error_code or self.error_code
        self.status_code = status_code or self.status_code

    def to_response_body(self, *, trace_id: str | None = None) -> dict[str, Any]:
        """Return the default JSON response body for service handlers."""

        body: dict[str, Any] = {
            "detail": self.message,
            "error_code": self.error_code,
        }
        response_trace_id = trace_id or self.trace_id

        if self.details is not None:
            body["details"] = self.details

        if response_trace_id:
            body["trace_id"] = response_trace_id

        return body


class BadRequestError(ServiceError):
    status_code = 400
    error_code = "bad_request"


class UnauthorizedError(ServiceError):
    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(ServiceError):
    status_code = 403
    error_code = "forbidden"


class NotFoundError(ServiceError):
    status_code = 404
    error_code = "not_found"


class ConflictError(ServiceError):
    status_code = 409
    error_code = "conflict"


class FailedDependencyError(ServiceError):
    status_code = 424
    error_code = "failed_dependency"


class InternalServiceError(ServiceError):
    status_code = 500
    error_code = "internal_service_error"
