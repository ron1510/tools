from __future__ import annotations

from fastapi_observability import build_in_memory_metrics, build_resource_attributes
from fastapi_settings import BaseFastAPISettings


def test_build_resource_attributes_uses_shared_service_identity() -> None:
    settings = BaseFastAPISettings.model_validate(
        {
            "service_name": "demo-api",
            "service_namespace": "platform",
            "deployment_environment": "test",
        }
    )

    attributes = build_resource_attributes(settings)

    assert attributes["service.name"] == "demo-api"
    assert attributes["service.namespace"] == "platform"
    assert attributes["deployment.environment"] == "test"


def test_build_in_memory_metrics_can_record_a_counter() -> None:
    in_memory = build_in_memory_metrics({"service.name": "demo-api"})
    meter = in_memory.provider.get_meter("demo", "internal")
    counter = meter.create_counter("demo_counter")

    counter.add(1)
    payload = in_memory.reader.get_metrics_data()
    assert payload is not None
    resource_metrics = payload.resource_metrics

    assert resource_metrics is not None
