from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any

from fastapi_app_state import FastAPIAppState
from fastapi_state import TtlSnapshotStore


@dataclass(slots=True)
class DemoServiceAppState:
    runtime: FastAPIAppState
    database: sqlite3.Connection
    cache: TtlSnapshotStore[str]
    ticks_total: int = 0
    last_tick_ms: int = 0
    last_payload: str = ""
    items_seen: int = 0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def mark_tick(self, payload: str) -> None:
        with self._lock:
            self.ticks_total += 1
            self.last_tick_ms = _now_ms()
            self.last_payload = payload
            self.items_seen += 1
            self.runtime.register_metadata("last_payload", payload)
            self.cache.upsert(f"tick-{self.ticks_total}", payload)
            self.database.execute(
                "INSERT INTO ticks(payload, created_at_ms) VALUES (?, ?)",
                (payload, self.last_tick_ms),
            )
            self.database.commit()
            if self.ticks_total >= 1:
                self.runtime.mark_ready()

    def stats(self) -> dict[str, Any]:
        return {
            "ticks_total": self.ticks_total,
            "last_tick_ms": self.last_tick_ms,
            "last_payload": self.last_payload,
            "items_seen": self.items_seen,
            "cache": self.cache.stats(),
            "runtime": self.runtime.summary(),
            "database_ticks": self._database_tick_count(),
        }

    def ready(self) -> bool:
        return self.runtime.ready and self.ticks_total > 0

    def _database_tick_count(self) -> int:
        cursor = self.database.execute("SELECT COUNT(*) FROM ticks")
        row = cursor.fetchone()
        return int(row[0] if row is not None else 0)


def build_demo_state(service_name: str, service_namespace: str, deployment_environment: str, ttl_seconds: int, max_items: int) -> DemoServiceAppState:
    runtime = FastAPIAppState(
        service_name=service_name,
        service_namespace=service_namespace,
        deployment_environment=deployment_environment,
    )
    database = sqlite3.connect(":memory:", check_same_thread=False)
    database.execute(
        "CREATE TABLE ticks (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL, created_at_ms INTEGER NOT NULL)"
    )
    database.commit()
    runtime.register_resource("database", database, database.close)
    cache = TtlSnapshotStore[str](ttl_seconds=ttl_seconds, max_items=max_items)
    runtime.register_resource("cache", cache)
    runtime.register_metadata("cache_ttl_seconds", ttl_seconds)
    runtime.register_metadata("cache_max_items", max_items)
    return DemoServiceAppState(runtime=runtime, database=database, cache=cache)


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)
