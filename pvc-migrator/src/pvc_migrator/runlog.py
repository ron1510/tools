from __future__ import annotations

import json
from pathlib import Path

from pvc_migrator.models import CommandExecutionRecord, RunLog


class RunLogStore:
    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root or ".pvc-migrator-runs")
        self._root.mkdir(parents=True, exist_ok=True)

    def load(self, run_id: str) -> RunLog:
        path = self._path_for(run_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return RunLog.model_validate(payload)

    def save(self, run_log: RunLog) -> Path:
        path = self._path_for(run_log.run_id)
        path.write_text(run_log.model_dump_json(indent=2), encoding="utf-8")
        return path

    def append_record(self, run_id: str, plan_summary: str, record: CommandExecutionRecord) -> RunLog:
        try:
            current = self.load(run_id)
            records = list(current.records)
        except FileNotFoundError:
            current = RunLog(run_id=run_id, plan_summary=plan_summary)
            records = []
        records.append(record)
        updated = RunLog(run_id=run_id, plan_summary=plan_summary, records=tuple(records))
        self.save(updated)
        return updated

    def completed_commands(self, run_id: str) -> set[str]:
        try:
            current = self.load(run_id)
        except FileNotFoundError:
            return set()
        return {record.command for record in current.records if record.status == "completed"}

    def _path_for(self, run_id: str) -> Path:
        return self._root / f"{run_id}.json"
