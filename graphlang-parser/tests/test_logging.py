from __future__ import annotations

import logging

import pytest

from opium_parser import compile_ast_to_gremlin, compile_opium_to_gremlin, parse_opium
from opium_parser.errors import (
    InvalidOpiumSemanticError,
    UnsupportedOpiumSyntaxError,
)
from tests.compiler.expected_gremlin import VERTEX_DOCUMENT_STEP


def record_for(caplog: pytest.LogCaptureFixture, event: str) -> logging.LogRecord:
    return next(record for record in caplog.records if record.event == event)


def test_parse_success_logs_source_ast_kind_and_duration(caplog):
    source = "get('users').limit(2)"
    caplog.set_level(logging.INFO, logger="opium_parser.parser")

    query = parse_opium(source)

    record = record_for(caplog, "opium.parse.succeeded")
    assert record.levelno == logging.INFO
    assert record.opium_source == source
    assert record.opium_source_length == len(source)
    assert record.ast_root_kind == query.root.kind
    assert record.parse_duration_ms >= 0


def test_source_compile_logs_once_without_nested_parser_success(caplog):
    source = "get('users').limit(2)"
    expected = "g.V().hasLabel('users').limit(2)" f"{VERTEX_DOCUMENT_STEP}"
    caplog.set_level(logging.INFO, logger="opium_parser")

    assert compile_opium_to_gremlin(source) == expected

    record = record_for(caplog, "opium.compile.succeeded")
    assert record.levelno == logging.INFO
    assert record.opium_source == source
    assert record.gremlin_query == expected
    assert record.gremlin_query_length == len(expected)
    assert record.parse_duration_ms >= 0
    assert record.compile_duration_ms >= 0
    assert record.total_duration_ms >= 0
    assert not any(
        item.event == "opium.parse.succeeded"
        for item in caplog.records
        if hasattr(item, "event")
    )


def test_ast_compile_logs_without_source_text(caplog):
    query = parse_opium("get('users')")
    caplog.clear()
    caplog.set_level(logging.INFO, logger="opium_parser.compiler")

    compile_ast_to_gremlin(query)

    record = record_for(caplog, "opium.compile.succeeded")
    assert record.gremlin_query == "g.V().hasLabel('users')" f"{VERTEX_DOCUMENT_STEP}"
    assert not hasattr(record, "opium_source")
    assert record.compile_duration_ms >= 0
    assert record.total_duration_ms >= 0


def test_parse_failure_logs_structured_warning_without_traceback(caplog):
    source = "get('users').limit(1 + 2)"
    caplog.set_level(logging.WARNING, logger="opium_parser.parser")

    with pytest.raises(UnsupportedOpiumSyntaxError) as exc_info:
        parse_opium(source)

    record = record_for(caplog, "opium.parse.failed")
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert record.opium_source == source
    assert record.error_code == exc_info.value.detail.code
    assert record.error_stage == exc_info.value.detail.stage
    assert record.error_message == exc_info.value.detail.message
    assert record.error_context == dict(exc_info.value.detail.context)


def test_compile_failure_logs_structured_warning_without_traceback(caplog):
    source = "get('users').traverse(direction='sideways')"
    caplog.set_level(logging.WARNING, logger="opium_parser.compiler")

    with pytest.raises(InvalidOpiumSemanticError) as exc_info:
        compile_opium_to_gremlin(source)

    record = record_for(caplog, "opium.compile.failed")
    assert record.levelno == logging.WARNING
    assert record.exc_info is None
    assert record.opium_source == source
    assert record.error_code == exc_info.value.detail.code
    assert record.error_expected == exc_info.value.detail.expected
    assert record.error_actual == exc_info.value.detail.actual
    assert record.parse_duration_ms >= 0
    assert record.compile_duration_ms >= 0
    assert record.total_duration_ms >= 0


def test_unexpected_compile_failure_logs_traceback(caplog, monkeypatch):
    from opium_parser import compiler

    source = "get('users')"
    caplog.set_level(logging.ERROR, logger="opium_parser.compiler")

    def fail(_query):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(compiler, "_compile_query", fail)

    with pytest.raises(RuntimeError, match="internal failure"):
        compile_opium_to_gremlin(source)

    record = record_for(caplog, "opium.compile.internal_error")
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.opium_source == source


def test_unexpected_parse_failure_logs_traceback(caplog, monkeypatch):
    from opium_parser import parser

    source = "get('users')"
    caplog.set_level(logging.ERROR, logger="opium_parser.parser")

    def fail(_source):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(parser, "_parse_opium", fail)

    with pytest.raises(RuntimeError, match="internal failure"):
        parse_opium(source)

    record = record_for(caplog, "opium.parse.internal_error")
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.opium_source == source


def test_package_logger_uses_only_a_null_handler():
    logger = logging.getLogger("opium_parser")

    assert logger.propagate is True
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
