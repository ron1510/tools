"""Helpers for working with optional package dependencies."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from package.exceptions import OptionalDependencyError


def optional_import(
    module_name: str,
    *,
    feature: str | None = None,
    install_hint: str | None = None,
    package: str | None = None,
) -> ModuleType:
    """Import an optional dependency or raise an actionable ``ImportError``.

    Args:
        module_name: The module to import, such as ``"rich"`` or ``".client"``.
        feature: The feature that needs this dependency.
        install_hint: A command or short hint for installing the dependency.
        package: Package anchor for relative imports, matching
            ``importlib.import_module``.

    Returns:
        The imported module.

    Raises:
        OptionalDependencyError: If the module cannot be imported.
    """

    try:
        return import_module(module_name, package=package)
    except ImportError as exc:
        dependency = _display_name(module_name, package)
        raise OptionalDependencyError(
            dependency,
            feature=feature,
            install_hint=install_hint,
            original_error=exc,
        ) from exc


def _display_name(module_name: str, package: str | None) -> str:
    if module_name.startswith(".") and package:
        return f"{package}{module_name}"
    return module_name
