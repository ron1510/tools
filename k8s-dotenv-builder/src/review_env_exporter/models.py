from __future__ import annotations

from typing import Any, Final, Literal, Mapping, TypeAlias, final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from review_env_exporter.constants import (
    EXPORT_LABEL,
    HELM_INSTANCE_LABEL,
    KUBE_AUTH_MODE_AUTO,
    KUBE_AUTH_MODE_IN_CLUSTER,
    KUBE_AUTH_MODE_KUBECONFIG,
    KubeAuthMode,
    ROUTE_KIND,
    SERVICE_KIND,
    ResourceKind,
    SUPPORTED_RESOURCE_KINDS,
)

RawResource: TypeAlias = Mapping[str, Any]


@final
class EnvEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    value: str
    source_kind: str
    source_name: str


@final
class ResourceMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str = "<unknown-name>"
    namespace: str | None = None
    labels: Mapping[str, str] = Field(default_factory=dict)
    annotations: Mapping[str, str] = Field(default_factory=dict)

    @property
    def exportable(self) -> bool:
        return self.labels.get(EXPORT_LABEL) == "true"


@final
class RouteSpec(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    host: str
    tls: Mapping[str, Any] | None = None
    path: str | None = None


@final
class ServicePort(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str | None = None
    nodePort: int | None = None
    port: int | None = None
    targetPort: int | str | None = None


@final
class ServiceSpec(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str | None = None
    ports: tuple[ServicePort, ...] = Field(default_factory=tuple)


class BaseKubernetesResource(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    apiVersion: str | None = None
    kind: str
    metadata: ResourceMetadata = Field(default_factory=ResourceMetadata)

    def model_mapping(self) -> dict[str, Any]:
        return self.model_dump(mode="python", exclude_none=True)


@final
class RouteResource(BaseKubernetesResource):
    kind: Literal["Route"] = ROUTE_KIND
    spec: RouteSpec


@final
class ServiceResource(BaseKubernetesResource):
    kind: Literal["Service"] = SERVICE_KIND
    spec: ServiceSpec


@final
class GenericResource(BaseKubernetesResource):
    spec: Mapping[str, Any] = Field(default_factory=dict)


@final
class ResourceSelectionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    namespace: str
    helm_release_name: str | None = None
    label_selector: str | None = None
    resource_kinds: frozenset[ResourceKind] = Field(
        default_factory=lambda: SUPPORTED_RESOURCE_KINDS
    )

    def includes(self, kind: ResourceKind) -> bool:
        return kind in self.resource_kinds

    @property
    def effective_label_selector(self) -> str | None:
        selectors: list[str] = []
        if self.helm_release_name:
            selectors.append(f"{HELM_INSTANCE_LABEL}={self.helm_release_name}")
        if self.label_selector:
            selectors.append(self.label_selector)
        if not selectors:
            return None
        return ",".join(selectors)


@final
class ClusterAccessConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    auth_mode: KubeAuthMode = KUBE_AUTH_MODE_AUTO
    kubeconfig_path: str | None = None
    kube_context: str | None = None

    @model_validator(mode="after")
    def validate_auth_mode(self) -> "ClusterAccessConfig":
        if self.auth_mode == KUBE_AUTH_MODE_IN_CLUSTER and (
            self.kubeconfig_path is not None or self.kube_context is not None
        ):
            raise ValueError(
                "in-cluster auth does not accept kubeconfig_path or kube_context"
            )
        if self.auth_mode == KUBE_AUTH_MODE_KUBECONFIG and self.kubeconfig_path == "":
            raise ValueError("kubeconfig_path must not be empty")
        return self


KubernetesResource = RouteResource | ServiceResource | GenericResource
NormalizedResource: TypeAlias = BaseKubernetesResource
SelectedResource: TypeAlias = RouteResource | ServiceResource
DEFAULT_RESOURCE_KINDS: Final[frozenset[ResourceKind]] = SUPPORTED_RESOURCE_KINDS
NormalizedResources: TypeAlias = tuple[BaseKubernetesResource, ...]


def parse_kubernetes_resource(
    resource: RawResource | BaseKubernetesResource,
) -> BaseKubernetesResource:
    if isinstance(resource, BaseKubernetesResource):
        return resource
    base_resource = BaseKubernetesResource.model_validate(resource)
    if base_resource.kind == ROUTE_KIND:
        return RouteResource.model_validate(resource)
    if base_resource.kind == SERVICE_KIND:
        return ServiceResource.model_validate(resource)
    return GenericResource.model_validate(resource)
