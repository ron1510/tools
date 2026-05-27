from __future__ import annotations

import math

import pytest

from package import OptionalDependencyError, optional_import


def test_optional_import_returns_imported_module() -> None:
    assert optional_import("math") is math


def test_optional_import_raises_optional_dependency_error_for_missing_module() -> None:
    with pytest.raises(OptionalDependencyError) as exc_info:
        optional_import(
            "definitely_missing_optional_dependency_xyz",
            feature="test feature",
            install_hint="pip install definitely-missing",
        )

    message = str(exc_info.value)

    assert "Optional dependency 'definitely_missing_optional_dependency_xyz' could not be imported." in message
    assert "It is required for test feature." in message
    assert "Install it with: pip install definitely-missing" in message
    assert "Original error:" in message


def test_optional_import_adds_default_install_hint() -> None:
    with pytest.raises(OptionalDependencyError) as exc_info:
        optional_import("missing_package.submodule")

    assert "pip install missing_package" in str(exc_info.value)
