from __future__ import annotations

import sys
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tests.factories import make_happy_path_resources  # noqa: E402


@pytest.fixture
def happy_path_resources() -> list[dict[str, Any]]:
    return make_happy_path_resources()


@pytest.fixture
def resource_mutator(
    happy_path_resources: list[dict[str, Any]],
) -> Callable[[], list[dict[str, Any]]]:
    def factory() -> list[dict[str, Any]]:
        return deepcopy(happy_path_resources)

    return factory
