from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from typing import Any, cast


def test_fastapi_demo_service_runs_as_subprocess_and_shuts_down_cleanly(tmp_path: Path) -> None:
    port = 9181
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["SERVICE_NAME"] = "demo-api"
    env["APP_HOST"] = "127.0.0.1"
    env["APP_PORT"] = str(port)
    env["WORKER_TICK_INTERVAL_SECONDS"] = "0.05"
    env["OTEL_METRICS_ENABLED"] = "false"

    process = subprocess.Popen(
        [sys.executable, "-m", "fastapi_demo_service"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    try:
        deadline = time.time() + 10
        stats_payload: dict[str, object] | None = None
        while time.time() < deadline:
            try:
                stats_payload = _fetch_json(port, "/demo/state")
                if _as_int(stats_payload["ticks_total"]) > 0:
                    break
            except Exception:
                time.sleep(0.1)
                continue
            time.sleep(0.1)

        assert stats_payload is not None
        assert _as_int(stats_payload["ticks_total"]) > 0
        if hasattr(signal, "CTRL_BREAK_EVENT"):
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
        exit_code = process.wait(timeout=10)
        assert exit_code in (0, 3)
    finally:
        if process.poll() is None:
            process.kill()


def _fetch_json(port: int, path: str) -> dict[str, object]:
    with urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _as_int(value: object) -> int:
    return int(cast(Any, value))
