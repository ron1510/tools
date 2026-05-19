from __future__ import annotations

from pydantic import Field

from fastapi_settings import BaseFastAPISettings


class DemoFastAPISettings(BaseFastAPISettings):
    tick_interval_seconds: float = Field(default=0.2, alias="WORKER_TICK_INTERVAL_SECONDS")
    state_ttl_seconds: int = Field(default=60, alias="WORKER_STATE_TTL_SECONDS")
    max_state_items: int = Field(default=1000, alias="WORKER_MAX_STATE_ITEMS")
