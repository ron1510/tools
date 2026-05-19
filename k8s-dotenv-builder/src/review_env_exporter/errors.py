from __future__ import annotations

from typing import Any, Mapping, final


def resource_identity(resource: Mapping[str, Any]) -> tuple[str, str]:
    kind = str(resource.get("kind", "<unknown-kind>"))
    metadata = resource.get("metadata", {})
    if isinstance(metadata, Mapping):
        name = str(metadata.get("name", "<unknown-name>"))
    else:
        name = "<unknown-name>"
    return kind, name


class ReviewEnvExporterError(ValueError):
    """Base class for contract and export errors."""


@final
class FetchResourcesError(ReviewEnvExporterError):
    """Raised when a provider cannot fetch or normalize resources."""


@final
class MissingAnnotationError(ReviewEnvExporterError):
    def __init__(self, resource: Mapping[str, Any], annotation: str) -> None:
        kind, name = resource_identity(resource)
        super().__init__(f"{kind}/{name} is missing required annotation {annotation!r}")


@final
class UnsupportedExportTypeError(ReviewEnvExporterError):
    def __init__(self, resource: Mapping[str, Any], export_type: str) -> None:
        kind, name = resource_identity(resource)
        super().__init__(f"{kind}/{name} uses unsupported export type {export_type!r}")


@final
class WrongResourceKindError(ReviewEnvExporterError):
    def __init__(
        self,
        resource: Mapping[str, Any],
        expected_kind: str,
        details: str | None = None,
    ) -> None:
        kind, name = resource_identity(resource)
        message = f"{kind}/{name} must be a {expected_kind}"
        if details:
            message = f"{message}: {details}"
        super().__init__(message)


@final
class DuplicateEnvVarNameError(ReviewEnvExporterError):
    def __init__(
        self, env_name: str, first_source: str, second_resource: Mapping[str, Any]
    ) -> None:
        second_kind, second_name = resource_identity(second_resource)
        super().__init__(
            f"Duplicate env var name {env_name!r} from {first_source} and {second_kind}/{second_name}"
        )


@final
class NodePortPortNameRequiredError(ReviewEnvExporterError):
    def __init__(self, resource: Mapping[str, Any], annotation_name: str) -> None:
        kind, name = resource_identity(resource)
        super().__init__(
            f"{kind}/{name} has multiple NodePort entries and requires annotation {annotation_name!r}"
        )


@final
class ResourceContractErrorGroup(ReviewEnvExporterError):
    def __init__(self, errors: tuple[ReviewEnvExporterError, ...]) -> None:
        self.errors = errors
        summary = "\n".join(f"- {error}" for error in errors)
        super().__init__(
            f"Encountered {len(errors)} resource contract error(s):\n{summary}"
        )
