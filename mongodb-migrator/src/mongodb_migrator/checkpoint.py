from __future__ import annotations

import json
from pathlib import Path

from mongodb_migrator.errors import CheckpointError
from mongodb_migrator.models import CheckpointState


class CheckpointStore:
    def load(self, path: str | None) -> CheckpointState:
        if path is None:
            return CheckpointState()
        target = Path(path)
        if not target.exists():
            return CheckpointState()
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CheckpointError(f"invalid checkpoint file {target}: {exc}") from exc
        return CheckpointState.model_validate(payload)

    def save(self, path: str | None, state: CheckpointState) -> None:
        if path is None:
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )
