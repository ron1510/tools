from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("REVIEW_ENV_RUN_KIND_SMOKE") != "1",
    reason="Set REVIEW_ENV_RUN_KIND_SMOKE=1 to run the kind smoke integration test.",
)
def test_kind_smoke_export_matches_expected_output() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    command = [
        sys.executable,
        "-m",
        "review_env_exporter",
        "--namespace",
        "review-smoke",
        "--label-selector",
        "review.my-company.io/export-env=true",
        "--auth-mode",
        "kubeconfig",
        "--log-level",
        "ERROR",
    ]

    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stderr == ""
    assert completed.stdout == (
        "# Generated review environment file\n"
        "# Do not edit manually; regenerate from cluster resource metadata.\n"
        "\n"
        "# from Route/api\n"
        "API_URL=https://api.review-smoke.localtest.me/api\n"
        "\n"
        "# from Service/kafka-external\n"
        "KAFKA_BOOTSTRAP_SERVERS=nodeport-gw.review.example.com:32110\n"
        "\n"
        "# from Service/mongodb-external\n"
        "MONGODB_HOSTPORT=nodeport-gw.review.example.com:32217\n"
        "\n"
        "# from Route/ui\n"
        "UI_URL=http://ui.review-smoke.localtest.me\n"
    )
