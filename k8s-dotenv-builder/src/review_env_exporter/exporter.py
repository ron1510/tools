from __future__ import annotations

from typing import Final, Iterable, Mapping

from review_env_exporter.constants import (
    ANNOTATION_ENV_NAME,
    ANNOTATION_EXPORT_TYPE,
    ANNOTATION_PATH,
    ANNOTATION_PORT_NAME,
    ANNOTATION_PUBLIC_HOST,
    ANNOTATION_SCHEME,
    EXPORT_TYPE_NODEPORT_HOSTPORT,
    EXPORT_TYPE_ROUTE_URL,
)
from review_env_exporter.errors import (
    DuplicateEnvVarNameError,
    MissingAnnotationError,
    NodePortPortNameRequiredError,
    ResourceContractErrorGroup,
    ReviewEnvExporterError,
    UnsupportedExportTypeError,
    WrongResourceKindError,
)
from review_env_exporter.models import (
    BaseKubernetesResource,
    EnvEntry,
    RawResource,
    RouteResource,
    ServicePort,
    ServiceResource,
    parse_kubernetes_resource,
)

_DOTENV_SAFE_CHARACTERS: Final[frozenset[str]] = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._:/"
)


def generate_env(resources: Iterable[RawResource | BaseKubernetesResource]) -> str:
    return render_dotenv(collect_env_entries(resources))


def collect_env_entries(
    resources: Iterable[RawResource | BaseKubernetesResource],
) -> list[EnvEntry]:
    entries: list[EnvEntry] = []
    errors: list[ReviewEnvExporterError] = []
    seen: dict[str, EnvEntry] = {}

    for raw_resource in resources:
        resource = parse_kubernetes_resource(raw_resource)
        if not resource.metadata.exportable:
            continue

        try:
            annotations = resource.metadata.annotations
            env_name = require_annotation(resource, annotations, ANNOTATION_ENV_NAME)
            export_type = require_annotation(
                resource, annotations, ANNOTATION_EXPORT_TYPE
            )

            if export_type == EXPORT_TYPE_ROUTE_URL:
                value = export_route_url(resource)
            elif export_type == EXPORT_TYPE_NODEPORT_HOSTPORT:
                value = export_nodeport_hostport(resource)
            else:
                raise UnsupportedExportTypeError(resource.model_mapping(), export_type)

            entry = EnvEntry(
                name=env_name,
                value=value,
                source_kind=resource.kind,
                source_name=resource.metadata.name,
            )

            previous_entry = seen.get(entry.name)
            if previous_entry is not None:
                raise DuplicateEnvVarNameError(
                    env_name=entry.name,
                    first_source=f"{previous_entry.source_kind}/{previous_entry.source_name}",
                    second_resource=resource.model_mapping(),
                )

            seen[entry.name] = entry
            entries.append(entry)
        except ReviewEnvExporterError as error:
            errors.append(error)

    if errors:
        raise ResourceContractErrorGroup(tuple(errors))

    return sorted(entries, key=lambda entry: entry.name)


def render_dotenv(entries: Iterable[EnvEntry]) -> str:
    lines: list[str] = [
        "# Generated review environment file",
        "# Do not edit manually; regenerate from cluster resource metadata.",
    ]

    for entry in entries:
        lines.append("")
        lines.append(f"# from {entry.source_kind}/{entry.source_name}")
        lines.append(f"{entry.name}={format_dotenv_value(entry.value)}")

    return "\n".join(lines) + "\n"


def export_route_url(resource: RawResource | BaseKubernetesResource) -> str:
    parsed = parse_kubernetes_resource(resource)
    if not isinstance(parsed, RouteResource):
        raise WrongResourceKindError(parsed.model_mapping(), "Route")

    annotations = parsed.metadata.annotations
    scheme = annotations.get(ANNOTATION_SCHEME) or (
        "https" if parsed.spec.tls is not None else "http"
    )
    path = annotations.get(ANNOTATION_PATH, parsed.spec.path)
    return f"{scheme}://{parsed.spec.host}{normalize_path(path)}"


def export_nodeport_hostport(resource: RawResource | BaseKubernetesResource) -> str:
    parsed = parse_kubernetes_resource(resource)
    if not isinstance(parsed, ServiceResource):
        raise WrongResourceKindError(parsed.model_mapping(), "Service")
    if parsed.spec.type != "NodePort":
        raise WrongResourceKindError(
            parsed.model_mapping(), "Service", 'spec.type must be "NodePort"'
        )

    public_host = require_annotation(
        parsed, parsed.metadata.annotations, ANNOTATION_PUBLIC_HOST
    )
    nodeport_ports = [port for port in parsed.spec.ports if port.nodePort is not None]
    if not nodeport_ports:
        raise WrongResourceKindError(
            parsed.model_mapping(),
            "Service",
            'spec.ports must include at least one "nodePort"',
        )

    port_name = parsed.metadata.annotations.get(ANNOTATION_PORT_NAME)
    if len(nodeport_ports) > 1 and not port_name:
        raise NodePortPortNameRequiredError(
            parsed.model_mapping(), ANNOTATION_PORT_NAME
        )

    selected_port = select_nodeport_port(parsed, nodeport_ports, port_name)
    return f"{public_host}:{selected_port.nodePort}"


def require_annotation(
    resource: BaseKubernetesResource,
    annotations: Mapping[str, str],
    annotation_name: str,
) -> str:
    value = annotations.get(annotation_name)
    if value is None or value == "":
        raise MissingAnnotationError(resource.model_mapping(), annotation_name)
    return value


def select_nodeport_port(
    resource: BaseKubernetesResource,
    ports: Iterable[ServicePort],
    port_name: str | None,
) -> ServicePort:
    candidates = tuple(ports)
    if port_name is None:
        return candidates[0]

    for port in candidates:
        if port.name == port_name:
            return port

    raise WrongResourceKindError(
        resource.model_mapping(), "Service", f"no NodePort named {port_name!r} found"
    )


def normalize_path(path: str | None) -> str:
    if path is None or path == "":
        return ""
    if path.startswith("/"):
        return path
    return f"/{path}"


def format_dotenv_value(value: str) -> str:
    if value and all(char in _DOTENV_SAFE_CHARACTERS for char in value):
        return value

    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'
