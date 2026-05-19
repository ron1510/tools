from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from typing import Any, Callable, final

from pydantic import ValidationError

try:
    from kubernetes import client as kubernetes_client
    from kubernetes import config as kubernetes_config
except ImportError:
    kubernetes_client = None
    kubernetes_config = None

from review_env_exporter.constants import ROUTE_KIND, SERVICE_KIND
from review_env_exporter.errors import FetchResourcesError
from review_env_exporter.models import (
    ClusterAccessConfig,
    NormalizedResources,
    ResourceSelectionConfig,
    parse_kubernetes_resource,
)

RawResourceBatch = tuple[dict[str, Any], ...]
RouteFetcher = Callable[[str, str | None], Iterable[dict[str, Any]]]
ServiceFetcher = Callable[[str, str | None], Iterable[dict[str, Any]]]


@final
class KubernetesApiResourceProvider:
    def __init__(
        self,
        *,
        route_fetcher: RouteFetcher | None = None,
        service_fetcher: ServiceFetcher | None = None,
        access_config: ClusterAccessConfig | None = None,
    ) -> None:
        self._route_fetcher = route_fetcher or self._default_route_fetcher
        self._service_fetcher = service_fetcher or self._default_service_fetcher
        self._access_config = access_config or ClusterAccessConfig()

    @lru_cache(maxsize=32)
    def list_resources(self, config: ResourceSelectionConfig) -> NormalizedResources:
        raw_resources: list[dict[str, Any]] = []

        try:
            if config.includes(ROUTE_KIND):
                raw_resources.extend(
                    self._list_routes_cached(
                        config.namespace, config.effective_label_selector
                    )
                )
            if config.includes(SERVICE_KIND):
                raw_resources.extend(
                    self._list_services_cached(
                        config.namespace, config.effective_label_selector
                    )
                )
        except Exception as exc:
            raise FetchResourcesError(
                f"Failed to fetch resources from Kubernetes API: {exc}"
            ) from exc

        try:
            return tuple(
                parse_kubernetes_resource(resource) for resource in raw_resources
            )
        except ValidationError as exc:
            raise FetchResourcesError(
                f"Fetched resource payload failed validation: {exc}"
            ) from exc

    def clear_cache(self) -> None:
        self.list_resources.cache_clear()
        self._list_routes_cached.cache_clear()
        self._list_services_cached.cache_clear()
        self._get_kube_clients.cache_clear()

    @lru_cache(maxsize=32)
    def _list_routes_cached(
        self, namespace: str, label_selector: str | None
    ) -> RawResourceBatch:
        return tuple(self._route_fetcher(namespace, label_selector))

    @lru_cache(maxsize=32)
    def _list_services_cached(
        self, namespace: str, label_selector: str | None
    ) -> RawResourceBatch:
        return tuple(self._service_fetcher(namespace, label_selector))

    def _default_route_fetcher(
        self, namespace: str, label_selector: str | None
    ) -> Iterable[dict[str, Any]]:
        _, _, custom_objects_api = self._get_kube_clients()
        try:
            response = custom_objects_api.list_namespaced_custom_object(
                group="route.openshift.io",
                version="v1",
                namespace=namespace,
                plural="routes",
                label_selector=label_selector,
            )
        except Exception as exc:
            raise FetchResourcesError(
                f"Failed to list OpenShift routes in namespace {namespace!r}: {exc}"
            ) from exc

        items = response.get("items", [])
        if not isinstance(items, list):
            raise FetchResourcesError(
                "Route API response did not contain an 'items' list."
            )
        return items

    def _default_service_fetcher(
        self, namespace: str, label_selector: str | None
    ) -> Iterable[dict[str, Any]]:
        api_client, core_v1_api, _ = self._get_kube_clients()
        try:
            response = core_v1_api.list_namespaced_service(
                namespace=namespace, label_selector=label_selector
            )
        except Exception as exc:
            raise FetchResourcesError(
                f"Failed to list Services in namespace {namespace!r}: {exc}"
            ) from exc

        items = getattr(response, "items", None)
        if items is None:
            raise FetchResourcesError(
                "Service API response did not contain an items collection."
            )
        return [self._serialize_service(api_client, item) for item in items]

    @lru_cache(maxsize=1)
    def _get_kube_clients(self) -> tuple[Any, Any, Any]:
        if kubernetes_client is None or kubernetes_config is None:
            raise FetchResourcesError(
                "Kubernetes client dependency is not installed. Install with `pip install -e .[kubernetes]`."
            )

        try:
            if self._access_config.auth_mode == "kubeconfig":
                kubernetes_config.load_kube_config(
                    config_file=self._access_config.kubeconfig_path,
                    context=self._access_config.kube_context,
                )
            elif self._access_config.auth_mode == "in-cluster":
                kubernetes_config.load_incluster_config()
            else:
                try:
                    kubernetes_config.load_incluster_config()
                except Exception:
                    kubernetes_config.load_kube_config(
                        config_file=self._access_config.kubeconfig_path,
                        context=self._access_config.kube_context,
                    )
            api_client = kubernetes_client.ApiClient()
            return (
                api_client,
                kubernetes_client.CoreV1Api(api_client),
                kubernetes_client.CustomObjectsApi(api_client),
            )
        except Exception as exc:
            raise FetchResourcesError(
                f"Failed to initialize Kubernetes API clients: {exc}"
            ) from exc

    def _serialize_service(self, api_client: Any, item: Any) -> dict[str, Any]:
        payload = api_client.sanitize_for_serialization(item)
        if not isinstance(payload, dict):
            raise FetchResourcesError(
                "Service API serialization did not return an object payload."
            )
        payload["apiVersion"] = payload.get("apiVersion") or "v1"
        payload["kind"] = payload.get("kind") or SERVICE_KIND
        return payload
