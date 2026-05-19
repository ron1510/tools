from typing import Final, Literal

ResourceKind = Literal["Route", "Service"]
ExportType = Literal["route-url", "nodeport-hostport"]
KubeAuthMode = Literal["auto", "kubeconfig", "in-cluster"]

EXPORT_LABEL: Final[str] = "review.my-company.io/export-env"
ANNOTATION_ENV_NAME: Final[str] = "review.my-company.io/env-name"
ANNOTATION_EXPORT_TYPE: Final[str] = "review.my-company.io/export-type"
ANNOTATION_SCHEME: Final[str] = "review.my-company.io/scheme"
ANNOTATION_PATH: Final[str] = "review.my-company.io/path"
ANNOTATION_PUBLIC_HOST: Final[str] = "review.my-company.io/public-host"
ANNOTATION_PORT_NAME: Final[str] = "review.my-company.io/port-name"
HELM_INSTANCE_LABEL: Final[str] = "app.kubernetes.io/instance"

ROUTE_KIND: Final[Literal["Route"]] = "Route"
SERVICE_KIND: Final[Literal["Service"]] = "Service"

EXPORT_TYPE_ROUTE_URL: Final[Literal["route-url"]] = "route-url"
EXPORT_TYPE_NODEPORT_HOSTPORT: Final[Literal["nodeport-hostport"]] = "nodeport-hostport"

SUPPORTED_RESOURCE_KINDS: Final[frozenset[ResourceKind]] = frozenset(
    {ROUTE_KIND, SERVICE_KIND}
)
SUPPORTED_EXPORT_TYPES: Final[frozenset[ExportType]] = frozenset(
    {EXPORT_TYPE_ROUTE_URL, EXPORT_TYPE_NODEPORT_HOSTPORT}
)
KUBE_AUTH_MODE_AUTO: Final[KubeAuthMode] = "auto"
KUBE_AUTH_MODE_KUBECONFIG: Final[KubeAuthMode] = "kubeconfig"
KUBE_AUTH_MODE_IN_CLUSTER: Final[KubeAuthMode] = "in-cluster"
