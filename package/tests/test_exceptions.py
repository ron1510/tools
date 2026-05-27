from __future__ import annotations

from package import (
    BadRequestError,
    ConflictError,
    FailedDependencyError,
    ForbiddenError,
    InternalServiceError,
    NotFoundError,
    OptionalDependencyError,
    ServiceError,
    UnauthorizedError,
)


def test_optional_dependency_error_keeps_context() -> None:
    original = ImportError("No module named 'example'")

    error = OptionalDependencyError(
        "example",
        feature="example feature",
        install_hint="pip install example",
        original_error=original,
    )

    assert error.dependency == "example"
    assert error.feature == "example feature"
    assert error.install_hint == "pip install example"
    assert error.original_error is original
    assert "Optional dependency 'example' could not be imported." in str(error)
    assert "Original error: No module named 'example'" in str(error)


def test_service_error_response_body_omits_missing_details() -> None:
    error = ServiceError("Something failed")

    assert error.status_code == 500
    assert error.error_code == "service_error"
    assert error.to_response_body() == {
        "detail": "Something failed",
        "error_code": "service_error",
    }


def test_service_error_response_body_includes_details() -> None:
    error = FailedDependencyError(
        "Database unavailable",
        details={"dependency": "postgres"},
    )

    assert error.status_code == 424
    assert error.error_code == "failed_dependency"
    assert error.to_response_body() == {
        "detail": "Database unavailable",
        "error_code": "failed_dependency",
        "details": {"dependency": "postgres"},
    }


def test_service_error_response_body_includes_trace_id() -> None:
    error = ServiceError(
        "Something failed",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    )

    assert error.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert error.to_response_body() == {
        "detail": "Something failed",
        "error_code": "service_error",
        "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    }


def test_service_error_response_body_allows_trace_id_override() -> None:
    error = ServiceError(
        "Something failed",
        trace_id="11111111111111111111111111111111",
    )

    assert error.to_response_body(trace_id="22222222222222222222222222222222") == {
        "detail": "Something failed",
        "error_code": "service_error",
        "trace_id": "22222222222222222222222222222222",
    }


def test_service_error_allows_instance_overrides() -> None:
    error = ServiceError("Custom failure", error_code="custom", status_code=418)

    assert error.error_code == "custom"
    assert error.status_code == 418


def test_http_style_error_defaults() -> None:
    expected = [
        (BadRequestError, 400, "bad_request"),
        (UnauthorizedError, 401, "unauthorized"),
        (ForbiddenError, 403, "forbidden"),
        (NotFoundError, 404, "not_found"),
        (ConflictError, 409, "conflict"),
        (FailedDependencyError, 424, "failed_dependency"),
        (InternalServiceError, 500, "internal_service_error"),
    ]

    for error_type, status_code, error_code in expected:
        error = error_type("Message")
        assert error.status_code == status_code
        assert error.error_code == error_code
