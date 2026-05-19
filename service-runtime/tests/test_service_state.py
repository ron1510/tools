from __future__ import annotations

import time

from fastapi_state import TtlSnapshotStore


def test_ttl_snapshot_store_evicts_old_items() -> None:
    store = TtlSnapshotStore[str](ttl_seconds=1, max_items=10)
    store.upsert("old", "value", updated_at_ms=1)
    store.upsert("new", "value", updated_at_ms=int(time.time() * 1000))

    assert "new" in store.snapshot()
    assert "old" not in store.snapshot()
