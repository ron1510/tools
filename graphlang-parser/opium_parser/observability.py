"""Internal helpers for structured parser and compiler logging."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter_ns
from typing import Final

from opium_parser.errors import OpiumErrorDetail

PARSE_STARTED: Final = "opium.parse.started"
PARSE_SUCCEEDED: Final = "opium.parse.succeeded"
PARSE_FAILED: Final = "opium.parse.failed"
PARSE_INTERNAL_ERROR: Final = "opium.parse.internal_error"

COMPILE_STARTED: Final = "opium.compile.started"
COMPILE_SUCCEEDED: Final = "opium.compile.succeeded"
COMPILE_FAILED: Final = "opium.compile.failed"
COMPILE_INTERNAL_ERROR: Final = "opium.compile.internal_error"


def start_timer() -> int:
    return perf_counter_ns()


def elapsed_ms(start_ns: int) -> float:
    return (perf_counter_ns() - start_ns) / 1_000_000


def source_fields(source: str) -> dict[str, object]:
    return {
        "opium_source": source,
        "opium_source_length": len(source),
    }


def error_fields(detail: OpiumErrorDetail) -> dict[str, object]:
    span = None if detail.span is None else detail.span.model_dump(mode="json")
    return {
        "error_code": detail.code,
        "error_stage": detail.stage,
        "error_message": detail.message,
        "error_hint": detail.hint,
        "error_expected": detail.expected,
        "error_actual": detail.actual,
        "error_context": dict(detail.context),
        "error_span": span,
    }


def event_fields(event: str, **fields: object) -> Mapping[str, object]:
    return {"event": event, **fields}
