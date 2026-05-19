from __future__ import annotations

import threading
import time
from typing import Generic, TypeVar


ValueT = TypeVar("ValueT")


def _now_ms() -> int:
    return int(time.time() * 1000)


class TtlSnapshotStore(Generic[ValueT]):
    def __init__(self, ttl_seconds: int, max_items: int) -> None:
        self._ttl_ms = ttl_seconds * 1000
        self._max_items = max_items
        self._lock = threading.RLock()
        self._items: dict[str, tuple[int, ValueT]] = {}
        self._dropped_items = 0

    def upsert(self, key: str, value: ValueT, *, updated_at_ms: int | None = None) -> bool:
        timestamp = _now_ms() if updated_at_ms is None else updated_at_ms
        with self._lock:
            if len(self._items) >= self._max_items and key not in self._items:
                self._dropped_items += 1
                return False
            self._items[key] = (timestamp, value)
            self._evict_locked(_now_ms())
            return True

    def snapshot(self) -> dict[str, ValueT]:
        with self._lock:
            self._evict_locked(_now_ms())
            return {key: value for key, (_, value) in self._items.items()}

    def stats(self) -> dict[str, int]:
        with self._lock:
            self._evict_locked(_now_ms())
            return {
                "size": len(self._items),
                "dropped_items": self._dropped_items,
                "max_items": self._max_items,
            }

    def _evict_locked(self, now_ms: int) -> None:
        cutoff = now_ms - self._ttl_ms
        stale_keys = [key for key, (timestamp, _) in self._items.items() if timestamp < cutoff]
        for key in stale_keys:
            del self._items[key]
