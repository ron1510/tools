from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

from review_env_exporter import (
    ANNOTATION_ENV_NAME,
    ANNOTATION_EXPORT_TYPE,
    ClusterAccessConfig,
    DuplicateEnvVarNameError,
    EnvEntry,
    FetchResourcesError,
    HELM_INSTANCE_LABEL,
    MissingAnnotationError,
    NodePortPortNameRequiredError,
    ResourceContractErrorGroup,
    ResourceSelectionConfig,
    ReviewEnvExporterService,
    UnsupportedExportTypeError,
    WrongResourceKindError,
    collect_env_entries,
    export_nodeport_hostport,
    generate_env,
    render_dotenv,
)
from review_env_exporter.providers import (
    KubernetesApiResourceProvider,
    StaticResourceProvider,
)
from tests.factories import (
    make_happy_path_resources,
    make_internal_service,
    make_nodeport_service,
)


def _assert_group_contains(
    exc_info: pytest.ExceptionInfo[ResourceContractErrorGroup],
    expected_error_type: type[Exception],
) -> None:
    assert any(
        isinstance(error, expected_error_type) for error in exc_info.value.errors
    )


@dataclass
class FetcherSpy:
    return_value: list[dict[str, Any]]
    should_raise: Exception | None = None
    calls: list[tuple[str, str | None]] = field(default_factory=list)

    def __call__(
        self, namespace: str, label_selector: str | None
    ) -> list[dict[str, Any]]:
        self.calls.append((namespace, label_selector))
        if self.should_raise is not None:
            raise self.should_raise
        return self.return_value


@pytest.fixture
def expected_dotenv() -> str:
    return (
        "# Generated review environment file\n"
        "# Do not edit manually; regenerate from cluster resource metadata.\n"
        "\n"
        "# from Route/api\n"
        "API_URL=https://acme-feature-x.apps.cluster.example.com/api\n"
        "\n"
        "# from Service/kafka-external\n"
        "KAFKA_BOOTSTRAP_SERVERS=nodeport-gw.review.example.com:32110\n"
        "\n"
        "# from Service/mongodb-external\n"
        "MONGODB_HOSTPORT=nodeport-gw.review.example.com:32217\n"
        "\n"
        "# from Route/ui\n"
        "UI_URL=https://acme-feature-x.apps.cluster.example.com\n"
    )


@pytest.fixture
def selection_config() -> ResourceSelectionConfig:
    return ResourceSelectionConfig(namespace="review")


@pytest.fixture
def kubernetes_fetcher_spies(
    happy_path_resources: list[dict[str, Any]],
) -> tuple[FetcherSpy, FetcherSpy]:
    route_fetcher = FetcherSpy(
        return_value=[happy_path_resources[0], happy_path_resources[1]]
    )
    service_fetcher = FetcherSpy(return_value=happy_path_resources[2:4])
    return route_fetcher, service_fetcher


def test_generates_expected_dotenv_from_mock_resources(
    happy_path_resources: list[dict[str, Any]],
    expected_dotenv: str,
) -> None:
    assert generate_env(happy_path_resources) == expected_dotenv


def test_ignores_resources_without_export_label() -> None:
    assert collect_env_entries([make_internal_service()]) == []


@pytest.mark.parametrize(
    ("mutate", "expected_error_type"),
    [
        (
            lambda resources: resources[0]["metadata"]["annotations"].pop(
                ANNOTATION_ENV_NAME
            ),
            MissingAnnotationError,
        ),
        (
            lambda resources: resources[0]["metadata"]["annotations"].pop(
                ANNOTATION_EXPORT_TYPE
            ),
            MissingAnnotationError,
        ),
        (
            lambda resources: resources[1]["metadata"]["annotations"].__setitem__(
                ANNOTATION_ENV_NAME, "API_URL"
            ),
            DuplicateEnvVarNameError,
        ),
        (
            lambda resources: resources[0]["metadata"]["annotations"].__setitem__(
                ANNOTATION_EXPORT_TYPE, "secret-ref"
            ),
            UnsupportedExportTypeError,
        ),
    ],
)
def test_collect_env_entries_contract_errors(
    resource_mutator: Callable[[], list[dict[str, Any]]],
    mutate: Callable[[list[dict[str, Any]]], object],
    expected_error_type: type[Exception],
) -> None:
    resources = resource_mutator()
    mutate(resources)

    with pytest.raises(ResourceContractErrorGroup) as exc_info:
        collect_env_entries(resources)

    _assert_group_contains(exc_info, expected_error_type)


@pytest.mark.parametrize(
    ("resource", "expected_exception"),
    [
        (
            make_nodeport_service(
                name="bad-service",
                env_name="BAD_SERVICE",
                public_host="nodeport-gw.review.example.com",
                service_type="ClusterIP",
                ports=[{"name": "http", "nodePort": 32080}],
            ),
            WrongResourceKindError,
        ),
        (
            make_nodeport_service(
                name="multi-port-service",
                env_name="MULTI",
                public_host="nodeport-gw.review.example.com",
                ports=[
                    {"name": "http", "nodePort": 32080},
                    {"name": "https", "nodePort": 32443},
                ],
            ),
            NodePortPortNameRequiredError,
        ),
    ],
)
def test_nodeport_hostport_validation_errors(
    resource: dict[str, Any],
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception):
        export_nodeport_hostport(resource)


def test_selects_correct_nodeport_when_port_name_is_provided() -> None:
    resource = make_nodeport_service(
        name="multi-port-service",
        env_name="MULTI",
        public_host="nodeport-gw.review.example.com",
        port_name="https",
        ports=[
            {"name": "http", "nodePort": 32080},
            {"name": "https", "nodePort": 32443},
        ],
    )

    assert export_nodeport_hostport(resource) == "nodeport-gw.review.example.com:32443"


def test_correctly_quotes_dotenv_values_that_need_quoting() -> None:
    entries = [
        EnvEntry(
            name="GREETING",
            value='hello "review"\nnext line',
            source_kind="ConfigMap",
            source_name="example",
        )
    ]

    rendered = render_dotenv(entries)
    assert 'GREETING="hello \\"review\\"\\nnext line"\n' in rendered


def test_service_generates_env_from_provider(
    happy_path_resources: list[dict[str, Any]],
    selection_config: ResourceSelectionConfig,
) -> None:
    service = ReviewEnvExporterService(
        provider=StaticResourceProvider(happy_path_resources),
        config=selection_config,
    )

    rendered = service.generate_env()
    assert "API_URL=https://acme-feature-x.apps.cluster.example.com/api\n" in rendered


def test_kubernetes_provider_validates_and_returns_resources(
    kubernetes_fetcher_spies: tuple[FetcherSpy, FetcherSpy],
    selection_config: ResourceSelectionConfig,
) -> None:
    route_fetcher, service_fetcher = kubernetes_fetcher_spies
    provider = KubernetesApiResourceProvider(
        route_fetcher=route_fetcher,
        service_fetcher=service_fetcher,
    )

    resolved = provider.list_resources(selection_config)
    assert [resource.kind for resource in resolved] == [
        "Route",
        "Route",
        "Service",
        "Service",
    ]
    assert route_fetcher.calls == [("review", None)]
    assert service_fetcher.calls == [("review", None)]


def test_kubernetes_provider_wraps_fetch_errors(
    selection_config: ResourceSelectionConfig,
) -> None:
    provider = KubernetesApiResourceProvider(
        route_fetcher=FetcherSpy(return_value=[], should_raise=RuntimeError("boom")),
        service_fetcher=FetcherSpy(return_value=[]),
    )

    with pytest.raises(FetchResourcesError):
        provider.list_resources(selection_config)


def test_kubernetes_provider_caches_fetches_for_same_config(
    kubernetes_fetcher_spies: tuple[FetcherSpy, FetcherSpy],
    selection_config: ResourceSelectionConfig,
) -> None:
    route_fetcher, service_fetcher = kubernetes_fetcher_spies
    provider = KubernetesApiResourceProvider(
        route_fetcher=route_fetcher,
        service_fetcher=service_fetcher,
    )

    first = provider.list_resources(selection_config)
    second = provider.list_resources(selection_config)

    assert first == second
    assert route_fetcher.calls == [("review", None)]
    assert service_fetcher.calls == [("review", None)]


def test_kubernetes_provider_reuses_kind_cache_across_selection_configs(
    kubernetes_fetcher_spies: tuple[FetcherSpy, FetcherSpy],
) -> None:
    route_fetcher, service_fetcher = kubernetes_fetcher_spies
    provider = KubernetesApiResourceProvider(
        route_fetcher=route_fetcher,
        service_fetcher=service_fetcher,
    )

    provider.list_resources(
        ResourceSelectionConfig(namespace="review", resource_kinds=frozenset({"Route"}))
    )
    provider.list_resources(ResourceSelectionConfig(namespace="review"))

    assert route_fetcher.calls == [("review", None)]
    assert service_fetcher.calls == [("review", None)]


def test_kubernetes_provider_filters_by_helm_release_name(
    kubernetes_fetcher_spies: tuple[FetcherSpy, FetcherSpy],
) -> None:
    route_fetcher, service_fetcher = kubernetes_fetcher_spies
    provider = KubernetesApiResourceProvider(
        route_fetcher=route_fetcher,
        service_fetcher=service_fetcher,
    )

    provider.list_resources(
        ResourceSelectionConfig(namespace="review", helm_release_name="feature-123")
    )

    expected_selector = f"{HELM_INSTANCE_LABEL}=feature-123"
    assert route_fetcher.calls == [("review", expected_selector)]
    assert service_fetcher.calls == [("review", expected_selector)]


def test_resource_selection_config_combines_helm_release_and_label_selector() -> None:
    config = ResourceSelectionConfig(
        namespace="review",
        helm_release_name="feature-123",
        label_selector="review.my-company.io/export-env=true",
    )

    assert (
        config.effective_label_selector
        == "app.kubernetes.io/instance=feature-123,review.my-company.io/export-env=true"
    )


def test_collect_env_entries_aggregates_multiple_contract_errors(
    resource_mutator: Callable[[], list[dict[str, Any]]],
) -> None:
    resources = resource_mutator()
    del resources[0]["metadata"]["annotations"][ANNOTATION_ENV_NAME]
    del resources[1]["metadata"]["annotations"][ANNOTATION_EXPORT_TYPE]

    with pytest.raises(ResourceContractErrorGroup) as exc_info:
        collect_env_entries(resources)

    assert len(exc_info.value.errors) == 2
    _assert_group_contains(exc_info, MissingAnnotationError)


def test_cluster_access_config_rejects_in_cluster_kubeconfig_mix() -> None:
    with pytest.raises(ValueError):
        ClusterAccessConfig(auth_mode="in-cluster", kubeconfig_path="C:/tmp/config")
