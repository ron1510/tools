from __future__ import annotations

import os
from typing import Any, Self, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class SettingsError(ValueError):
    """Raised when environment-backed settings are invalid."""


class EnvSettings(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    @classmethod
    def from_env(cls) -> Self:
        payload: dict[str, Any] = {}
        for name, field_info in cls.model_fields.items():
            env_name = _resolve_env_name(name, field_info)
            raw_value = os.getenv(env_name)
            if raw_value is None:
                continue
            payload[name] = _parse_raw_value(raw_value, field_info.annotation)
        try:
            return cls.model_validate(payload)
        except ValidationError as exc:
            raise SettingsError(str(exc)) from exc


class BaseFastAPISettings(EnvSettings):
    service_name: str = Field(alias="SERVICE_NAME")
    service_namespace: str = Field(default="default", alias="SERVICE_NAMESPACE")
    service_version: str = Field(default="image", alias="SERVICE_VERSION")
    deployment_environment: str = Field(default="dev", alias="DEPLOYMENT_ENVIRONMENT")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    otlp_endpoint: str = Field(default="http://127.0.0.1:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_export_interval_ms: int = Field(default=30000, alias="OTEL_EXPORT_INTERVAL_MS")
    otel_resource_attributes: tuple[str, ...] = Field(
        default_factory=tuple,
        alias="OTEL_RESOURCE_ATTRIBUTES",
    )
    otel_metrics_enabled: bool = Field(default=True, alias="OTEL_METRICS_ENABLED")
    otel_traces_enabled: bool = Field(default=False, alias="OTEL_TRACES_ENABLED")

    def resource_attributes_map(self) -> dict[str, str]:
        attributes: dict[str, str] = {}
        for entry in self.otel_resource_attributes:
            if "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                attributes[key] = value
        return attributes


def _resolve_env_name(name: str, field_info: Any) -> str:
    alias = getattr(field_info, "alias", None)
    if isinstance(alias, str) and alias:
        return alias
    return name.upper()


def _parse_raw_value(raw_value: str, annotation: Any) -> Any:
    if annotation is None:
        return raw_value
    origin = get_origin(annotation)
    if origin in (tuple, list, set):
        item_type = get_args(annotation)[0] if get_args(annotation) else str
        return tuple(_parse_scalar(part, item_type) for part in _split_csv(raw_value))
    return _parse_scalar(raw_value, annotation)


def _parse_scalar(raw_value: str, annotation: Any) -> Any:
    adapter = TypeAdapter(annotation)
    try:
        return adapter.validate_python(raw_value)
    except ValidationError:
        if annotation is bool:
            normalized = raw_value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "no", "n", "off"}:
                return False
        return adapter.validate_python(raw_value)


def _split_csv(raw_value: str) -> list[str]:
    return [part.strip() for part in raw_value.split(",") if part.strip()]
