from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request, Response
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi_settings import BaseFastAPISettings


@dataclass(frozen=True)
class TelemetryHandle:
    meter_provider: MeterProvider | None
    tracer_provider: TracerProvider | None

    def shutdown(self) -> None:
        if self.meter_provider is not None:
            self.meter_provider.shutdown()
        if self.tracer_provider is not None:
            self.tracer_provider.shutdown()


@dataclass(frozen=True)
class InMemoryMetrics:
    reader: InMemoryMetricReader
    provider: MeterProvider


def configure_telemetry(
    settings: BaseFastAPISettings,
    *,
    meter_name: str,
    meter_version: str = "internal",
) -> TelemetryHandle:
    resource = Resource.create(build_resource_attributes(settings))
    meter_provider: MeterProvider | None = None
    tracer_provider: TracerProvider | None = None

    if settings.otel_metrics_enabled:
        exporter = OTLPMetricExporter(
            endpoint=settings.otlp_endpoint,
            insecure=settings.otlp_endpoint.startswith("http://"),
        )
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=settings.otel_export_interval_ms,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
        metrics.get_meter(meter_name, meter_version)

    if settings.otel_traces_enabled:
        tracer_provider = TracerProvider(resource=resource)
        span_exporter = OTLPSpanExporter(
            endpoint=settings.otlp_endpoint,
            insecure=settings.otlp_endpoint.startswith("http://"),
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)

    return TelemetryHandle(
        meter_provider=meter_provider,
        tracer_provider=tracer_provider,
    )


def build_resource_attributes(settings: BaseFastAPISettings) -> dict[str, str]:
    attributes = {
        "service.name": settings.service_name,
        "service.namespace": settings.service_namespace,
        "service.version": settings.service_version,
        "deployment.environment": settings.deployment_environment,
    }
    attributes.update(settings.resource_attributes_map())
    return attributes


def build_in_memory_metrics(resource_attributes: dict[str, str]) -> InMemoryMetrics:
    reader = InMemoryMetricReader()
    provider = MeterProvider(resource=Resource.create(resource_attributes), metric_readers=[reader])
    return InMemoryMetrics(reader=reader, provider=provider)


class FastAPIMetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, meter_name: str, tracer_name: str) -> None:
        super().__init__(app)
        meter = metrics.get_meter(meter_name, "internal")
        self._request_counter = meter.create_counter(
            "fastapi_requests_total",
            description="Total HTTP requests observed by the shared FastAPI runtime.",
            unit="1",
        )
        self._request_latency = meter.create_histogram(
            "fastapi_request_duration_ms",
            description="HTTP request duration in milliseconds.",
            unit="ms",
        )
        self._tracer = trace.get_tracer(tracer_name, "internal")

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        start = time.perf_counter()
        with self._tracer.start_as_current_span(f"{request.method} {request.url.path}") as span:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            attributes = {
                "http.method": request.method,
                "http.route": request.url.path,
                "http.status_code": response.status_code,
            }
            self._request_counter.add(1, attributes)
            self._request_latency.record(duration_ms, attributes)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", request.url.path)
            span.set_attribute("http.status_code", response.status_code)
            return response
