"""Exception handling utilities for Python packages and services."""

from package.exceptions import (
    BadRequestError,
    ConflictError,
    FailedDependencyError,
    ForbiddenError,
    InternalServiceError,
    NotFoundError,
    OptionalDependencyError,
    PackageError,
    ServiceError,
    UnauthorizedError,
)
from package.imports import optional_import

__all__ = [
    "BadRequestError",
    "ConflictError",
    "FailedDependencyError",
    "ForbiddenError",
    "InternalServiceError",
    "NotFoundError",
    "OptionalDependencyError",
    "PackageError",
    "ServiceError",
    "UnauthorizedError",
    "optional_import",
]
