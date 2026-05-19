from __future__ import annotations

import pytest

from fastapi_settings import BaseFastAPISettings, SettingsError


def test_base_fastapi_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_NAME", "demo-worker")
    monkeypatch.setenv("APP_PORT", "9100")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "team=platform,region=us")
    monkeypatch.setenv("OTEL_METRICS_ENABLED", "true")

    settings = BaseFastAPISettings.from_env()

    assert settings.service_name == "demo-worker"
    assert settings.app_port == 9100
    assert settings.resource_attributes_map() == {"team": "platform", "region": "us"}
    assert settings.otel_metrics_enabled is True


def test_base_fastapi_settings_requires_service_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SERVICE_NAME", raising=False)

    with pytest.raises(SettingsError):
        BaseFastAPISettings.from_env()
